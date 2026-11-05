"""OpenAI-compatible chat client with pydantic validation and record/replay.

One HTTP call per structured request, temperature 0 and json_object responses.
A validation failure triggers exactly one repair retry with the error appended.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Protocol, TypeVar, runtime_checkable

import httpx
from pydantic import BaseModel, ValidationError

from ..config import LLMSettings, SplitbrainError, internet_client, redact
from .cassette import CassetteStore

SchemaT = TypeVar("SchemaT", bound=BaseModel)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_TRANSPORT_RETRIES = 5
MIN_INTERVAL_S = 0.35


class LLMResponseError(SplitbrainError):
    """The endpoint returned a status or a body we cannot use; fail loud."""


@runtime_checkable
class LLMTransport(Protocol):
    async def chat_json(self, system: str, user: str) -> dict[str, Any]: ...

    async def aclose(self) -> None: ...


def _strip_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


class HttpTransport:
    """Internet-facing transport: trust_env stays at httpx's default (True)."""

    def __init__(self, settings: LLMSettings, *, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or internet_client(timeout=httpx.Timeout(90.0))
        self._last_call = 0.0

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < MIN_INTERVAL_S:
            await asyncio.sleep(MIN_INTERVAL_S - elapsed)

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after", "")
        try:
            return min(float(header), 30.0)
        except ValueError:
            return min(1.5 * (2**attempt), 20.0)

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if self.settings.reasoning_effort:
            payload["reasoning_effort"] = self.settings.reasoning_effort
        headers = {"Authorization": f"Bearer {self.settings.api_key}"}
        response: httpx.Response | None = None
        for attempt in range(MAX_TRANSPORT_RETRIES + 1):
            await self._throttle()
            response = await self._client.post(
                f"{self.settings.base_url}/chat/completions", json=payload, headers=headers
            )
            self._last_call = time.monotonic()
            if response.status_code not in RETRY_STATUSES or attempt == MAX_TRANSPORT_RETRIES:
                break
            await asyncio.sleep(self._retry_delay(response, attempt))
        assert response is not None
        body = redact(response.text, (self.settings.api_key,))
        if response.status_code != 200:
            raise LLMResponseError(
                f"LLM chat/completions failed with HTTP {response.status_code}: {body}"
            )
        try:
            envelope = response.json()
            content = envelope["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                f"LLM chat/completions returned an unexpected body: {body}"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("LLM chat/completions returned an empty message content")
        try:
            parsed = json.loads(_strip_fences(content))
        except ValueError as exc:
            raise LLMResponseError(f"LLM response is not valid JSON: {body}") from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError(f"LLM response is not a JSON object: {body}")
        return parsed

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _brief(exc: ValidationError) -> str:
    return str(exc)[:1500]


class LLMClient:
    """Structured, cached model calls. Replay never constructs a transport."""

    def __init__(
        self,
        settings: LLMSettings,
        cassettes: CassetteStore,
        *,
        transport: LLMTransport | None = None,
    ) -> None:
        self.settings = settings
        self.cassettes = cassettes
        self.mode = settings.mode
        self._transport = transport

    @property
    def _live(self) -> LLMTransport:
        if self._transport is None:
            if self.mode == "replay":
                raise SplitbrainError(
                    "internal error: replay mode must not open a network connection"
                )
            self._transport = HttpTransport(self.settings)
        return self._transport

    async def structured(
        self,
        system: str,
        user: str,
        schema: type[SchemaT],
        *,
        context: dict[str, Any] | None = None,
    ) -> SchemaT:
        validation_context = context or {}
        raw = await self._live.chat_json(system, user)
        try:
            return schema.model_validate(raw, context=validation_context)
        except ValidationError as exc:
            repair = (
                f"{user}\n\nVALIDATION ERROR IN YOUR PREVIOUS RESPONSE:\n{_brief(exc)}\n"
                "Return the corrected JSON object only."
            )
            retry = await self._live.chat_json(system, repair)
            try:
                return schema.model_validate(retry, context=validation_context)
            except ValidationError as second:
                raise LLMResponseError(
                    f"LLM response failed validation twice for {schema.__name__}: {_brief(second)}"
                ) from second

    async def cached(
        self,
        *,
        task: str,
        key: str,
        description: str,
        input_payload: dict[str, Any],
        system: str,
        user: str,
        schema: type[SchemaT],
    ) -> SchemaT:
        if self.mode == "replay" or (
            self.mode == "record" and not self.cassettes.overwrite and self.cassettes.has(task, key)
        ):
            return schema.model_validate(self.cassettes.read(task, key, description))
        result = await self.structured(system, user, schema)
        self.cassettes.write(task, key, input_payload, result.model_dump(mode="json"))
        return result

    async def aclose(self) -> None:
        if self._transport is not None:
            await self._transport.aclose()
