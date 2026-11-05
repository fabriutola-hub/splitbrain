"""Semantic cassette keys, replay misses and the recorded-model field."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from splitbrain.core.extractor import Extractor
from splitbrain.core.models import ClaimStatus, ClassificationResult, Message
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


async def test_record_missing_never_overwrites_existing_cassettes(llm_factory) -> None:
    client, transport, store, _ = llm_factory(
        [
            {"relation": "contradiction", "confidence": 0.91, "reason": "New pair recorded."},
            {
                "results": [
                    {
                        "message_id": "m-new",
                        "claims": [
                            {
                                "subject": "SSO",
                                "scope": "Acme",
                                "subject_key": "sso",
                                "scope_key": "acme",
                                "polarity": "affirm",
                                "value": "December 1",
                                "effective_date": "2026-12-01",
                                "kind": "commitment",
                                "confidence": 0.9,
                            }
                        ],
                    }
                ]
            },
        ]
    )
    store.overwrite = False

    existing_classify = store.path("classify", "existing-pair")
    existing_classify.parent.mkdir(parents=True, exist_ok=True)
    original_classify_json = json.dumps(
        {
            "input": {"pair": "existing"},
            "model": "pinned/model-v0",
            "output": {
                "relation": "compatible",
                "confidence": 0.99,
                "reason": "Original cassette must stay untouched.",
            },
            "recorded_at": "2020-01-01T00:00:00+00:00",
            "task": "classify",
        },
        indent=2,
        sort_keys=True,
    )
    existing_classify.write_text(original_classify_json + "\n", encoding="utf-8")

    reused = await client.cached(
        task="classify",
        key="existing-pair",
        description="existing pair",
        input_payload={"pair": "would-overwrite"},
        system="sys",
        user="usr",
        schema=ClassificationResult,
    )
    assert reused.relation.value == "compatible"
    assert reused.reason == "Original cassette must stay untouched."
    assert len(transport.calls) == 0
    assert existing_classify.read_text(encoding="utf-8") == original_classify_json + "\n"

    recorded = await client.cached(
        task="classify",
        key="missing-pair",
        description="missing pair",
        input_payload={"pair": "new"},
        system="sys",
        user="usr",
        schema=ClassificationResult,
    )
    assert recorded.relation.value == "contradiction"
    assert len(transport.calls) == 1
    assert store.path("classify", "missing-pair").is_file()

    existing_text = "Acme gets SSO on December 15."
    existing_extract_key = extract_key(existing_text)
    existing_extract = store.path("extract", existing_extract_key)
    existing_extract.parent.mkdir(parents=True, exist_ok=True)
    original_extract_json = json.dumps(
        {
            "input": {"text": existing_text},
            "model": "pinned/model-v0",
            "output": {"message_id": "m-old", "claims": []},
            "recorded_at": "2020-01-01T00:00:00+00:00",
            "task": "extract",
        },
        indent=2,
        sort_keys=True,
    )
    existing_extract.write_text(original_extract_json + "\n", encoding="utf-8")

    extractor = Extractor(client)
    claims_existing = await extractor.extract_batch(
        [
            Message(
                message_id="m-old",
                room_id="r-sales",
                room_name="sales",
                channel_type="channel_public",
                author="maria",
                text=existing_text,
            )
        ]
    )
    assert claims_existing == {"m-old": []}
    assert len(transport.calls) == 1
    assert existing_extract.read_text(encoding="utf-8") == original_extract_json + "\n"

    claims_new = await extractor.extract_batch(
        [
            Message(
                message_id="m-new",
                room_id="r-support",
                room_name="support",
                channel_type="channel_public",
                author="lucia",
                text="Quick one for the desk: Acme gets SSO on December 1.",
            )
        ]
    )
    assert len(claims_new["m-new"]) == 1
    assert claims_new["m-new"][0].status == ClaimStatus.ACTIVE
    assert len(transport.calls) == 2
