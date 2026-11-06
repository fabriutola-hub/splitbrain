"""Structured LLM calls: payload, redaction, repair retry, replay isolation."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from splitbrain.config import LLMSettings
from splitbrain.core.models import ClassificationResult
from splitbrain.llm.cassette import CassetteStore
from splitbrain.llm.client import HttpTransport, LLMClient, LLMResponseError
from splitbrain.llm.prompts import EXTRACTION_SYSTEM


def _settings(tmp_path: Path, monkeypatch, *, effort: str | None = "none") -> LLMSettings:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "super-secret-key")
    monkeypatch.setenv("SPLITBRAIN_LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("SPLITBRAIN_LLM_MODEL", "unit/model")
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    if effort is None:
        monkeypatch.delenv("SPLITBRAIN_LLM_REASONING_EFFORT", raising=False)
    else:
        monkeypatch.setenv("SPLITBRAIN_LLM_REASONING_EFFORT", effort)
    return LLMSettings.load(mode="live")


def _completion(content: dict, *, usage: dict | None = None) -> httpx.Response:
    body: dict = {"choices": [{"message": {"content": json.dumps(content)}}]}
    if usage is not None:
        body["usage"] = usage
    return httpx.Response(200, json=body)


@respx.mock
async def test_http_payload_and_headers(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch)
    route = respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=_completion(
            {"relation": "contradiction", "confidence": 0.9, "reason": "Two dates."}
        )
    )
    transport = HttpTransport(settings)
    try:
        result = await transport.chat_json(EXTRACTION_SYSTEM, "user text")
    finally:
        await transport.aclose()
    assert result["relation"] == "contradiction"
    request = route.calls[0].request
    payload = json.loads(request.content)
    assert payload["model"] == "unit/model"
    assert payload["temperature"] == 0
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["reasoning_effort"] == "none"
    assert payload["messages"][0]["role"] == "system"
    assert request.headers["authorization"] == "Bearer super-secret-key"


@respx.mock
async def test_http_transport_tracks_latency_and_token_usage(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch)
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=_completion(
            {"relation": "contradiction", "confidence": 0.9, "reason": "Two dates."},
            usage={"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        )
    )
    client = LLMClient(
        settings,
        CassetteStore(tmp_path / "cassettes", model=settings.model, mode="live"),
    )
    try:
        await client.structured("system", "user", ClassificationResult)
        stats = client.stats()
    finally:
        await client.aclose()
    assert stats.calls == 1
    assert stats.mean_latency_s >= 0.0
    assert stats.usage_reported is True
    assert stats.prompt_tokens == 120
    assert stats.completion_tokens == 30
    assert stats.total_tokens == 150


@respx.mock
async def test_reasoning_content_is_ignored(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch, effort=None)
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "reasoning_content": "ignore me",
                            "content": (
                                '```json\n{"relation":"update","confidence":0.8,"reason":"ok"}\n```'
                            ),
                        }
                    }
                ]
            },
        )
    )
    transport = HttpTransport(settings)
    try:
        assert (await transport.chat_json("s", "u"))["relation"] == "update"
    finally:
        await transport.aclose()


@respx.mock
async def test_rate_limit_is_retried(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch)
    route = respx.post("https://llm.test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, text="slow down", headers={"Retry-After": "0"}),
            _completion({"relation": "update", "confidence": 0.8, "reason": "ok"}),
        ]
    )
    transport = HttpTransport(settings)
    try:
        assert (await transport.chat_json("s", "u"))["relation"] == "update"
    finally:
        await transport.aclose()
    assert len(route.calls) == 2


@respx.mock
async def test_unexpected_status_raises_without_the_key(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch)
    respx.post("https://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(401, text="bad key super-secret-key")
    )
    transport = HttpTransport(settings)
    try:
        with pytest.raises(LLMResponseError) as error:
            await transport.chat_json("s", "u")
    finally:
        await transport.aclose()
    assert "401" in str(error.value)
    assert "super-secret-key" not in str(error.value)
    assert "<redacted>" in str(error.value)


async def test_one_repair_retry_on_invalid_json(llm_factory) -> None:
    client, transport, _, _ = llm_factory(
        [
            {"relation": "not-a-relation", "confidence": 2, "reason": ""},
            {"relation": "compatible", "confidence": 0.9, "reason": "Two phases."},
        ],
        mode="live",
    )
    result = await client.structured("system", "user", ClassificationResult)
    assert result.relation.value == "compatible"
    assert len(transport.calls) == 2
    assert "VALIDATION ERROR" in transport.calls[1][1]
    await client.aclose()


async def test_second_validation_failure_raises(llm_factory) -> None:
    client, transport, _, _ = llm_factory(
        [{"relation": "bogus"}, {"relation": "still-bogus"}], mode="live"
    )
    with pytest.raises(LLMResponseError, match="failed validation twice"):
        await client.structured("system", "user", ClassificationResult)
    assert len(transport.calls) == 2
    await client.aclose()


async def test_replay_mode_refuses_to_build_a_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "unit-test-key")
    settings = LLMSettings.load(mode="replay")

    client = LLMClient(settings, CassetteStore(tmp_path, model=settings.model, mode="replay"))
    with pytest.raises(Exception, match="replay mode must not open"):
        await client.structured("system", "user", ClassificationResult)
