"""Async client for the Switch 0.31.0 agent protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from ..config import loopback_client, redact
from .events import (
    ConnectionStateFrame,
    GapFrame,
    GapPayload,
    SwitchFrame,
    parse_frame,
)
from .sse import SSEParser

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_S = 2.0
INITIAL_BACKOFF_S = 0.5
MAX_BACKOFF_S = 5.0

EventHandler = Callable[[SwitchFrame], Awaitable[None]]


class SwitchOpError(RuntimeError):
    """An operation failed; carries the operation name, HTTP status and body."""

    def __init__(self, op: str, status: int, body: str) -> None:
        self.op = op
        self.status = status
        self.body = body
        super().__init__(f"Switch operation {op!r} failed with HTTP {status}: {body}")


MISSING_ROOM_CONTEXT = "Not connected to a room. Call connect_to_room first."


def lost_room_context(exc: SwitchOpError) -> bool:
    """True when Switch refused a room-scoped call because the claim is gone.

    The claim is connection state, not a property of the agent: another
    connection of the same agent can take the room from this one between two
    calls, so a read that follows a successful connect can still find none.
    """
    if exc.status != 400:
        return False
    try:
        detail = json.loads(exc.body)
    except json.JSONDecodeError:
        return False
    return isinstance(detail, dict) and detail.get("detail") == MISSING_ROOM_CONTEXT


def transient_switch_error(exc: BaseException) -> bool:
    """True for a read failure a later attempt may survive.

    A lost room claim, a connection the server no longer holds, a dropped
    socket or a server error is transient. A rejected argument, a missing
    document or a permission error is not, and must stay visible.
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, SwitchOpError):
        return lost_room_context(exc) or exc.status == 409 or exc.status >= 500
    return False


class RegistrationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    api_key: str


class OpResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Any


@dataclass(frozen=True, slots=True)
class AgentCredentials:
    agent_id: str
    api_key: str


class SwitchAgent:
    """One agent, one connection id for the process lifetime, one room lock."""

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        api_key: str,
        *,
        connection_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self._api_key = api_key
        self.connection_id = connection_id or str(uuid.uuid4())
        self._owns_client = client is None
        self._client = client or loopback_client(timeout=httpx.Timeout(10.0, read=None))
        self._room_lock = asyncio.Lock()
        self._last_sequence = 0
        self._heartbeat_interval_s = DEFAULT_HEARTBEAT_INTERVAL_S
        self._pending_gap: GapPayload | None = None
        self._stream_response: httpx.Response | None = None
        self._reopen_requested = False
        self._reopen_immediate = False
        self.server_version: str | None = None

    @classmethod
    async def register(
        cls,
        base_url: str,
        registration_token: str,
        name: str,
        description: str,
        *,
        overwrite: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> AgentCredentials:
        payload = {
            "name": name,
            "description": description,
            "connector_type": "custom",
            "integration_profile": {
                "connection_model": "always_on",
                "message_exchange": True,
                "pre_invocation_mediation": [],
                "post_invocation_mediation": [],
                "event_reporting": [],
            },
            "overwrite": overwrite,
        }
        owns_client = client is None
        http = client or loopback_client(timeout=10.0)
        try:
            response = await http.post(
                f"{base_url.rstrip('/')}/agents",
                json=payload,
                headers={"Authorization": f"Bearer {registration_token}"},
            )
        finally:
            if owns_client:
                await http.aclose()
        if response.status_code != 200:
            raise SwitchOpError(
                "register_agent",
                response.status_code,
                redact(response.text, (registration_token,)),
            )
        result = RegistrationResult.model_validate(response.json())
        return AgentCredentials(agent_id=result.id, api_key=result.api_key)

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    # `name` is positional-only because several Switch ops take a `name` argument.
    # Room-agnostic ops can omit the connection header: the server rejects a
    # header naming a connection with no open stream (409).
    async def op(self, name: str, /, *, connection: bool = True, **args: Any) -> Any:
        headers = dict(self._auth_headers)
        if connection:
            headers["X-Switch-Connection-Id"] = self.connection_id
        response = await self._client.post(
            f"{self.base_url}/agents/{self.agent_id}/ops/{name}",
            json=args,
            headers=headers,
        )
        if response.status_code != 200:
            raise SwitchOpError(name, response.status_code, redact(response.text, (self._api_key,)))
        return OpResult.model_validate(response.json()).result

    @asynccontextmanager
    async def connect_in(self, room_id: str) -> AsyncIterator[dict[str, Any]]:
        """Claim the room under the connection lock and return the connect payload."""
        async with self._room_lock:
            yield await self.op("connect_to_room", room_id=room_id)

    @asynccontextmanager
    async def act_in(self, room_id: str) -> AsyncIterator[SwitchAgent]:
        """Serialize connect_to_room + the operation: the claim is connection state."""
        async with self.connect_in(room_id):
            yield self

    async def post(self, room_id: str, body: str, thread_id: str | None = None) -> Any:
        args: dict[str, Any] = {"body": body}
        if thread_id is not None:
            args["thread_id"] = thread_id
        async with self.act_in(room_id) as agent:
            return await agent.op("post_message", **args)

    async def targeted(
        self,
        room_id: str,
        body: str,
        *,
        target_names: list[str] | None = None,
        target_roles: list[str] | None = None,
        thread_id: str | None = None,
    ) -> Any:
        if not target_names and not target_roles:
            raise ValueError("targeted() needs target_names or target_roles")
        args: dict[str, Any] = {"body": body}
        if target_names:
            args["target_names"] = target_names
        if target_roles:
            args["target_roles"] = target_roles
        if thread_id is not None:
            args["thread_id"] = thread_id
        async with self.act_in(room_id) as agent:
            return await agent.op("send_targeted_message", **args)

    async def run(self, handler: EventHandler, *, stop: asyncio.Event | None = None) -> None:
        backoff = INITIAL_BACKOFF_S
        while stop is None or not stop.is_set():
            try:
                await self._stream_once(handler, stop=stop)
                backoff = INITIAL_BACKOFF_S
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Switch event stream failed; reopening the same connection")
            if stop is not None and stop.is_set():
                return
            if self._reopen_immediate:
                # A dead connection needs a new socket, not an exponential wait.
                self._reopen_immediate = False
                await self._sleep_or_stop(0.05, stop)
                backoff = INITIAL_BACKOFF_S
                continue
            await self._sleep_or_stop(backoff, stop)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    @staticmethod
    async def _sleep_or_stop(delay: float, stop: asyncio.Event | None) -> None:
        if stop is None:
            await asyncio.sleep(delay)
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            pass

    async def _stream_once(self, handler: EventHandler, *, stop: asyncio.Event | None) -> None:
        self._reopen_requested = False
        headers = {**self._auth_headers, "Accept": "text/event-stream"}
        if self._last_sequence > 0:
            headers["Last-Event-ID"] = str(self._last_sequence)
        params = {
            "connection_id": self.connection_id,
            "scope": "all",
            "filter": "all",
            "start_from": "head",
        }
        beat_task: asyncio.Task[None] | None = None
        try:
            async with self._client.stream(
                "GET",
                f"{self.base_url}/agents/{self.agent_id}/events",
                params=params,
                headers=headers,
                timeout=httpx.Timeout(10.0, read=None),
            ) as response:
                self._stream_response = response
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise SwitchOpError(
                        "events", response.status_code, redact(body, (self._api_key,))
                    )
                parser = SSEParser()
                async for chunk in response.aiter_bytes():
                    for sse_frame in parser.feed(chunk):
                        event = parse_frame(sse_frame)
                        if isinstance(event, ConnectionStateFrame):
                            self._apply_connection_state(event)
                            if beat_task is None:
                                beat_task = asyncio.create_task(self._heartbeat_loop())
                        if event.kind == "evicted":
                            logger.warning("Switch evicted this stream; reopening")
                            self._reopen_requested = True
                        await self._dispatch(handler, event)
                        if self._reopen_requested or (stop is not None and stop.is_set()):
                            return
        finally:
            self._stream_response = None
            if beat_task is not None:
                beat_task.cancel()
                await asyncio.gather(beat_task, return_exceptions=True)

    def _apply_connection_state(self, frame: ConnectionStateFrame) -> None:
        self._heartbeat_interval_s = max(0.01, float(frame.heartbeat_interval_seconds))
        self.server_version = frame.server.version
        self._last_sequence = max(self._last_sequence, frame.cursor)

    async def _dispatch(self, handler: EventHandler, event: SwitchFrame) -> None:
        if isinstance(event, GapFrame):
            logger.warning("Switch event gap: %s", event.reason or "cursor expired")
            self._pending_gap = GapPayload.model_validate(event.model_dump())
            return
        if event.sequence is not None and event.sequence > self._last_sequence:
            self._last_sequence = event.sequence
        if self._pending_gap is not None:
            event.gap = self._pending_gap
            self._pending_gap = None
        await handler(event)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval_s)
            try:
                response = await self._client.post(
                    f"{self.base_url}/agents/{self.agent_id}/connection/beat",
                    json={"connection_id": self.connection_id, "cursor": self._last_sequence},
                    headers=self._auth_headers,
                )
            except httpx.TransportError:
                logger.exception("Heartbeat transport failed; reopening the stream")
                await self._request_reopen()
                return
            if response.status_code in (404, 409):
                logger.warning(
                    "Heartbeat returned %s; reopening the stream (not backing off)",
                    response.status_code,
                )
                await self._request_reopen()
                return
            if response.status_code != 200:
                logger.error(
                    "Heartbeat returned %s: %s",
                    response.status_code,
                    redact(response.text, (self._api_key,)),
                )
                await self._request_reopen()
                return

    async def _request_reopen(self) -> None:
        self._reopen_requested = True
        self._reopen_immediate = True
        if self._stream_response is not None:
            await self._stream_response.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
