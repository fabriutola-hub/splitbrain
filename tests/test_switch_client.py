"""Unit tests for the Switch protocol client (no network: respx)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
import pytest
import respx

from splitbrain.switch.client import AgentCredentials, SwitchAgent, SwitchOpError
from splitbrain.switch.events import (
    ConnectionStateFrame,
    GapPayload,
    MessageFrame,
    SwitchFrame,
)

BASE = "http://switch.test"
AGENT_ID = "agent-1"
API_KEY = "api-key-secret"
BIG_SEQUENCE = 9007194959773697


def frame(event: str, data: dict[str, Any], *, frame_id: str | None = None) -> bytes:
    head = f"id: {frame_id}\n" if frame_id else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def connection_state(*, heartbeat: float = 0.02, cursor: int = 0) -> bytes:
    return frame(
        "connection_state",
        {
            "connection_id": "server-conn",
            "agent_id": AGENT_ID,
            "scope": "all",
            "filter": "all",
            "rooms": [],
            "cursor": cursor,
            "protocol": 9,
            "heartbeat_interval_seconds": heartbeat,
            "server": {"version": "0.31.0", "contracts": {}},
        },
    )


def message(sequence: int, body: str) -> bytes:
    return frame(
        "message",
        {
            "type": "message",
            "room_id": "room-1",
            "channel_type": "channel_public",
            "payload": {
                "addressed": False,
                "sender_name": "it-user",
                "message_id": "sw_1",
                "body": body,
                "timestamp": sequence,
                "thread_id": None,
            },
            "sequence": sequence,
        },
        frame_id=str(sequence),
    )


def sse_response(*frames: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=b"".join(frames),
        headers={"content-type": "text/event-stream"},
    )


def stream_route() -> respx.Route:
    return respx.get(url__regex=r".*/agents/agent-1/events")


def beat_route(**kwargs: Any) -> respx.Route:
    return respx.post(f"{BASE}/agents/{AGENT_ID}/connection/beat", **kwargs)


@respx.mock
async def test_register_sends_the_custom_profile() -> None:
    route = respx.post(f"{BASE}/agents").mock(
        return_value=httpx.Response(200, json={"id": "id-1", "api_key": "key-1"})
    )
    credentials = await SwitchAgent.register(BASE, "REG-TOKEN", "it-agent", "probe")
    assert credentials == AgentCredentials(agent_id="id-1", api_key="key-1")
    request = route.calls[0].request
    payload = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer REG-TOKEN"
    assert payload["connector_type"] == "custom"
    assert payload["integration_profile"] == {
        "connection_model": "always_on",
        "message_exchange": True,
        "pre_invocation_mediation": [],
        "post_invocation_mediation": [],
        "event_reporting": [],
    }
    assert payload["overwrite"] is False


@respx.mock
async def test_register_error_redacts_the_token() -> None:
    respx.post(f"{BASE}/agents").mock(return_value=httpx.Response(409, text="rejected REG-TOKEN"))
    with pytest.raises(SwitchOpError) as error:
        await SwitchAgent.register(BASE, "REG-TOKEN", "it-agent", "probe")
    assert error.value.op == "register_agent"
    assert error.value.status == 409
    assert "REG-TOKEN" not in str(error.value)
    assert "<redacted>" in str(error.value)


@respx.mock
async def test_op_returns_result_and_sends_the_connection_header() -> None:
    agent = SwitchAgent(BASE, AGENT_ID, API_KEY, connection_id="fixed-conn")
    route = respx.post(f"{BASE}/agents/{AGENT_ID}/ops/list_rooms").mock(
        return_value=httpx.Response(200, json={"result": [{"room_id": "r1"}]})
    )
    try:
        assert await agent.op("list_rooms") == [{"room_id": "r1"}]
        request = route.calls[0].request
        assert request.headers["x-switch-connection-id"] == "fixed-conn"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
    finally:
        await agent.aclose()


@respx.mock
async def test_op_can_omit_the_connection_header() -> None:
    agent = SwitchAgent(BASE, AGENT_ID, API_KEY, connection_id="fixed-conn")
    route = respx.post(f"{BASE}/agents/{AGENT_ID}/ops/get_room_detail").mock(
        return_value=httpx.Response(200, json={"result": {"name": "room"}})
    )
    try:
        assert await agent.op("get_room_detail", room_id="r1", connection=False) == {"name": "room"}
        assert "x-switch-connection-id" not in route.calls[0].request.headers
        assert json.loads(route.calls[0].request.content) == {"room_id": "r1"}
    finally:
        await agent.aclose()


@respx.mock
async def test_op_error_has_op_status_body_and_no_secret() -> None:
    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    respx.post(f"{BASE}/agents/{AGENT_ID}/ops/create_room").mock(
        return_value=httpx.Response(403, text=f"denied for {API_KEY}")
    )
    try:
        with pytest.raises(SwitchOpError) as error:
            await agent.op("create_room", name="x")
        assert error.value.op == "create_room"
        assert error.value.status == 403
        assert "create_room" in str(error.value)
        assert "403" in str(error.value)
        assert API_KEY not in str(error.value)
    finally:
        await agent.aclose()


@respx.mock
async def test_act_in_serializes_connect_and_post() -> None:
    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    respx.post(f"{BASE}/agents/{AGENT_ID}/ops/connect_to_room").mock(
        return_value=httpx.Response(200, json={"result": {"room_id": "r1"}})
    )
    respx.post(f"{BASE}/agents/{AGENT_ID}/ops/post_message").mock(
        return_value=httpx.Response(200, json={"result": {"event_id": "sw_1"}})
    )
    try:
        await asyncio.gather(
            agent.post("r1", "a"),
            agent.post("r2", "b", thread_id="sw_9"),
        )
        calls = list(respx.calls)
        assert [call.request.url.path.rsplit("/", 1)[-1] for call in calls] == [
            "connect_to_room",
            "post_message",
            "connect_to_room",
            "post_message",
        ]
        assert [json.loads(call.request.content) for call in calls] == [
            {"room_id": "r1"},
            {"body": "a"},
            {"room_id": "r2"},
            {"body": "b", "thread_id": "sw_9"},
        ]
    finally:
        await agent.aclose()


@respx.mock
async def test_targeted_sends_only_declared_arguments() -> None:
    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    respx.post(f"{BASE}/agents/{AGENT_ID}/ops/connect_to_room").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )
    route = respx.post(f"{BASE}/agents/{AGENT_ID}/ops/send_targeted_message").mock(
        return_value=httpx.Response(200, json={"result": {"event_id": "sw_2"}})
    )
    try:
        await agent.targeted("r1", "hi", target_roles=["verifier"], thread_id="sw_1")
        assert json.loads(route.calls[0].request.content) == {
            "body": "hi",
            "target_roles": ["verifier"],
            "thread_id": "sw_1",
        }
        with pytest.raises(ValueError, match="target_names"):
            await agent.targeted("r1", "hi")
    finally:
        await agent.aclose()


@respx.mock
async def test_run_reuses_connection_id_and_sends_last_event_id() -> None:
    stream_route().mock(
        side_effect=[
            sse_response(connection_state(), message(BIG_SEQUENCE, "hello")),
            sse_response(connection_state(cursor=BIG_SEQUENCE)),
            sse_response(connection_state(cursor=BIG_SEQUENCE)),
        ]
    )
    beat_route().mock(return_value=httpx.Response(200, json={"ok": True}))

    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    seen: list[SwitchFrame] = []
    stop = asyncio.Event()

    async def handler(event: SwitchFrame) -> None:
        seen.append(event)
        if isinstance(event, MessageFrame):
            await asyncio.sleep(0.08)  # let the heartbeat tick before the stream ends
        if sum(isinstance(item, ConnectionStateFrame) for item in seen) >= 2:
            stop.set()

    try:
        await agent.run(handler, stop=stop)
    finally:
        await agent.aclose()

    streams = [c for c in respx.calls if c.request.url.path.endswith("/events")]
    assert len(streams) >= 2
    assert all(c.request.url.params["connection_id"] == agent.connection_id for c in streams)
    assert all(c.request.url.params["scope"] == "all" for c in streams)
    assert all(c.request.url.params["filter"] == "all" for c in streams)
    assert "last-event-id" not in streams[0].request.headers
    assert streams[1].request.headers["last-event-id"] == str(BIG_SEQUENCE)
    assert any(isinstance(item, MessageFrame) and item.sequence == BIG_SEQUENCE for item in seen)

    beats = [c for c in respx.calls if c.request.url.path.endswith("/connection/beat")]
    assert beats
    beat_body = json.loads(beats[0].request.content)
    assert beat_body["connection_id"] == agent.connection_id
    assert beat_body["cursor"] == BIG_SEQUENCE
    assert agent.server_version == "0.31.0"


@pytest.mark.parametrize("dead_status", [404, 409])
@respx.mock
async def test_beat_dead_connection_reopens_without_a_long_backoff(dead_status: int) -> None:
    stream_route().mock(
        side_effect=[
            sse_response(connection_state()),
            sse_response(connection_state()),
            sse_response(connection_state()),
        ]
    )
    beat_calls = 0

    def beat(request: httpx.Request) -> httpx.Response:
        nonlocal beat_calls
        beat_calls += 1
        if beat_calls == 1:
            return httpx.Response(dead_status, json={"detail": "connection unknown"})
        return httpx.Response(200, json={"ok": True})

    beat_route().mock(side_effect=beat)

    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    stop = asyncio.Event()
    states = 0

    async def handler(event: SwitchFrame) -> None:
        nonlocal states
        if isinstance(event, ConnectionStateFrame):
            states += 1
            await asyncio.sleep(0.05)  # let the 404 heartbeat fire
            if states >= 2:
                stop.set()

    started = time.monotonic()
    try:
        await agent.run(handler, stop=stop)
    finally:
        await agent.aclose()
    elapsed = time.monotonic() - started

    streams = [c for c in respx.calls if c.request.url.path.endswith("/events")]
    assert len(streams) >= 2
    assert all(c.request.url.params["connection_id"] == agent.connection_id for c in streams)
    assert beat_calls >= 1
    assert elapsed < 1.0  # immediate reopen, not the 0.5 s+ backoff


@respx.mock
async def test_no_heartbeat_before_connection_state() -> None:
    stream_route().mock(return_value=sse_response(message(7, "no state frame")))
    beat_route().mock(return_value=httpx.Response(200, json={"ok": True}))

    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    stop = asyncio.Event()

    async def handler(event: SwitchFrame) -> None:
        if isinstance(event, MessageFrame):
            stop.set()

    try:
        await agent.run(handler, stop=stop)
    finally:
        await agent.aclose()

    beats = [c for c in respx.calls if c.request.url.path.endswith("/connection/beat")]
    assert beats == []


@respx.mock
async def test_gap_is_logged_and_attached_to_the_next_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gap = frame("gap", {"from_sequence": 1, "resumed_at": 2, "reason": "server restart"})
    stream_route().mock(
        return_value=sse_response(connection_state(heartbeat=0.2), gap, message(42, "after gap"))
    )

    agent = SwitchAgent(BASE, AGENT_ID, API_KEY)
    seen: list[SwitchFrame] = []
    stop = asyncio.Event()

    async def handler(event: SwitchFrame) -> None:
        seen.append(event)
        if isinstance(event, MessageFrame):
            stop.set()

    with caplog.at_level(logging.WARNING, logger="splitbrain.switch.client"):
        try:
            await agent.run(handler, stop=stop)
        finally:
            await agent.aclose()

    assert "Switch event gap" in caplog.text
    assert len(seen) == 2  # the gap itself did not wake the handler
    last = seen[-1]
    assert isinstance(last, MessageFrame)
    assert isinstance(last.gap, GapPayload)
    assert last.gap.reason == "server restart"
