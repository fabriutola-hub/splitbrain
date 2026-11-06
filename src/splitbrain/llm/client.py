"""OpenAI-compatible chat client with pydantic validation and record/replay.

One HTTP call per structured request, temperature 0 and json_object responses.
A validation failure triggers exactly one repair retry with the error appended.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class LLMCallStats:
    """Per-client call count, HTTP latency and token usage reported by the API."""

    calls: int = 0
    mean_latency_s: float = 0.0
    total_latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    usage_calls: int = 0

    @property
    def usage_reported(self) -> bool:
        return self.usage_calls > 0


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
        self.call_latencies_s: list[float] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.usage_calls = 0

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

    def _record_usage(self, envelope: dict[str, Any]) -> None:
        usage = envelope.get("usage")
        if not isinstance(usage, dict):
            return
        prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion = usage.get("completion_tokens", usage.get("output_tokens"))
        total = usage.get("total_tokens")
        if (
            isinstance(prompt, int)
            and not isinstance(prompt, bool)
            and isinstance(completion, int)
            and not isinstance(completion, bool)
        ):
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            total_val = (
                total
                if isinstance(total, int) and not isinstance(total, bool)
                else prompt + completion
            )
            self.total_tokens += total_val
            self.usage_calls += 1

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
            started = time.monotonic()
            response = await self._client.post(
                f"{self.settings.base_url}/chat/completions", json=payload, headers=headers
            )
            now = time.monotonic()
            self._last_call = now
            if response.status_code not in RETRY_STATUSES or attempt == MAX_TRANSPORT_RETRIES:
                self.call_latencies_s.append(now - started)
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
        self._record_usage(envelope)
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
        self._fallback_latencies: list[float] = []

    @property
    def _live(self) -> LLMTransport:
        if self._transport is None:
            if self.mode == "replay":
                raise SplitbrainError(
                    "internal error: replay mode must not open a network connection"
                )
            self._transport = HttpTransport(self.settings)
        return self._transport

    async def _call_live(self, system: str, user: str) -> dict[str, Any]:
        started = time.monotonic()
        result = await self._live.chat_json(system, user)
        self._fallback_latencies.append(time.monotonic() - started)
        return result

    def stats(self) -> LLMCallStats:
        transport = self._transport
        latencies = getattr(transport, "call_latencies_s", None)
        if not isinstance(latencies, list):
            latencies = self._fallback_latencies
        calls = len(latencies)
        total_latency = float(sum(latencies))
        mean_latency = total_latency / calls if calls else 0.0
        prompt_tokens = int(getattr(transport, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(transport, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(transport, "total_tokens", 0) or 0)
        usage_calls = int(getattr(transport, "usage_calls", 0) or 0)
        return LLMCallStats(
            calls=calls,
            mean_latency_s=mean_latency,
            total_latency_s=total_latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_calls=usage_calls,
        )

    async def structured(
        self,
        system: str,
        user: str,
        schema: type[SchemaT],
        *,
        context: dict[str, Any] | None = None,
    ) -> SchemaT:
        validation_context = context or {}
        raw = await self._call_live(system, user)
        try:
            return schema.model_validate(raw, context=validation_context)
        except ValidationError as exc:
            repair = (
                f"{user}\n\nVALIDATION ERROR IN YOUR PREVIOUS RESPONSE:\n{_brief(exc)}\n"
                "Return the corrected JSON object only."
            )
            retry = await self._call_live(system, repair)
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
