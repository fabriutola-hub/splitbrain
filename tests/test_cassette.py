"""Semantic cassette keys, replay misses and the recorded-model field."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from splitbrain.core.models import ClassificationResult
from splitbrain.llm.cassette import (
    CassetteStore,
    ReplayMiss,
    classify_key,
    extract_key,
    normalize_text,
)
from splitbrain.llm.client import LLMClient


def test_extract_key_is_semantic_not_literal() -> None:
    assert normalize_text("  SSO   ships  DECEMBER  1 ") == "sso ships december 1"
    assert extract_key("SSO ships December 1") == extract_key("  sso   ships december 1 ")
    assert extract_key("SSO ships December 1") != extract_key("SSO ships December 15")


def test_classify_key_is_independent_of_pair_order() -> None:
    assert classify_key("a|x", "b|y") == classify_key("b|y", "a|x")


def test_write_records_the_model_and_no_api_key(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path, model="unit/model-v1", mode="record")
    key = extract_key("SSO ships December 1")
    store.write("extract", key, {"text": "SSO ships December 1"}, {"message_id": "m1"})
    path = store.path("extract", key)
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    record = json.loads(content)
    assert record["task"] == "extract"
    assert record["model"] == "unit/model-v1"
    assert record["input"] == {"text": "SSO ships December 1"}
    assert record["output"] == {"message_id": "m1"}
    assert record["recorded_at"]
    assert "unit-test-key" not in content
    assert store.read("extract", key, "unit test") == {"message_id": "m1"}


def test_live_mode_does_not_write(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path, model="unit/model", mode="live")
    store.write("classify", "abc", {}, {})
    assert not (tmp_path / "classify").exists()


def test_replay_miss_names_the_input_and_explains_the_fix(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path, model="unit/model", mode="replay")
    with pytest.raises(ReplayMiss) as error:
        store.read("classify", "deadbeef", "pair sso/acme in #sales")
    message = str(error.value)
    assert "cassettes/classify/deadbeef.json" in message
    assert "pair sso/acme in #sales" in message
    assert "SPLITBRAIN_LLM_MODE=record uv run splitbrain eval" in message
    assert "SPLITBRAIN_LLM_API_KEY" in message


async def test_replay_never_opens_a_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "unit-test-key")
    from splitbrain.config import LLMSettings

    settings = LLMSettings.load(mode="replay")
    store = CassetteStore(tmp_path / "cassettes", model=settings.model, mode="replay")
    client = LLMClient(settings, store)
    with pytest.raises(ReplayMiss):
        await client.cached(
            task="classify",
            key="missing",
            description="pair sso/acme",
            input_payload={},
            system="sys",
            user="usr",
            schema=ClassificationResult,
        )
    assert client._transport is None


async def test_record_writes_one_semantic_cassette(llm_factory) -> None:
    client, transport, store, _ = llm_factory(
        [{"relation": "contradiction", "confidence": 0.9, "reason": "Two different dates."}]
    )
    result = await client.cached(
        task="classify",
        key="pair-1",
        description="pair sso/acme",
        input_payload={"pair": "a|b"},
        system="sys",
        user="usr",
        schema=ClassificationResult,
    )
    assert result.relation.value == "contradiction"
    assert len(transport.calls) == 1
    record = json.loads(store.path("classify", "pair-1").read_text(encoding="utf-8"))
    assert record["model"] == client.settings.model
    assert record["output"]["relation"] == "contradiction"
