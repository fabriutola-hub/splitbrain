"""End-to-end brain with a fake LLM: record, replay and the no-network guarantee."""

from __future__ import annotations

from pathlib import Path

from splitbrain.core.models import EvalPair, EvalSide, Relation
from splitbrain.core.pipeline import Brain


def _claim(message_id: str, value: str, polarity: str, scope_key: str) -> dict:
    return {
        "kind": "commitment" if polarity == "affirm" else "decision",
        "subject": "SSO",
        "subject_key": "sso",
        "scope": "Acme" if scope_key == "acme" else "*",
        "scope_key": scope_key,
        "value": value,
        "polarity": polarity,
        "effective_date": None,
        "confidence": 0.93,
    }


def _extraction(pair_id: str, second_scope: str = "*") -> dict:
    return {
        "results": [
            {
                "message_id": f"{pair_id}-a",
                "claims": [_claim("a", "live on 2026-12-01", "affirm", "acme")],
            },
            {
                "message_id": f"{pair_id}-b",
                "claims": [_claim("b", "removed from Q4", "negate", second_scope)],
            },
        ]
    }


def _classification(relation: str, confidence: float = 0.94) -> dict:
    return {"relation": relation, "confidence": confidence, "reason": "Two different dates."}


def _pair(pair_id: str, *, author_b: str = "tomas") -> EvalPair:
    return EvalPair(
        id=pair_id,
        a=EvalSide(
            room="sales",
            author="maria",
            text="Confirmed with Acme that SSO will be live for them on December 1.",
        ),
        b=EvalSide(
            room="engineering",
            author=author_b,
            text="We are pulling SSO out of Q4, the migration has to land first.",
        ),
        label=Relation.CONTRADICTION,
        note="unit test",
    )


async def test_contradiction_path_records_per_item_cassettes(llm_factory, tmp_path: Path) -> None:
    llm, transport, _, _ = llm_factory(
        [_extraction("p1"), _classification("contradiction")], mode="record"
    )
    brain = Brain(llm)
    try:
        result = await brain.analyze_pair(_pair("p1"))
    finally:
        await llm.aclose()
    assert result.predicted == "contradiction"
    assert result.candidate is True
    assert result.stage == "classification"
    assert result.confidence == 0.94
    assert len(transport.calls) == 2  # one batched extraction + one classification
    assert len(list((tmp_path / "cassettes" / "extract").glob("*.json"))) == 2
    assert len(list((tmp_path / "cassettes" / "classify").glob("*.json"))) == 1
    record = next((tmp_path / "cassettes" / "classify").glob("*.json")).read_text(encoding="utf-8")
    assert '"model"' in record
    assert "unit-test-key" not in record


async def test_replay_reproduces_the_same_result_without_a_transport(llm_factory) -> None:
    record_llm, _, _, _ = llm_factory(
        [_extraction("p2"), _classification("contradiction")], mode="record"
    )
    try:
        recorded = await Brain(record_llm).analyze_pair(_pair("p2"))
    finally:
        await record_llm.aclose()

    replay_llm, replay_transport, _, settings = llm_factory([], mode="replay")
    try:
        replayed = await Brain(replay_llm).analyze_pair(_pair("p2"))
    finally:
        await replay_llm.aclose()
    assert replay_transport.calls == []
    assert replayed.predicted == recorded.predicted == "contradiction"
    assert replayed.reason == recorded.reason
    assert replayed.confidence == recorded.confidence
    assert settings.mode == "replay"


async def test_same_author_revision_is_an_update_not_a_conflict(llm_factory) -> None:
    llm, transport, _, _ = llm_factory([_extraction("p3")], mode="live")
    try:
        result = await Brain(llm).analyze_pair(_pair("p3", author_b="maria"))
    finally:
        await llm.aclose()
    assert result.predicted == "update"
    assert result.stage == "matching"
    assert "same author" in result.reason
    assert len(transport.calls) == 1  # classification is never reached


async def test_different_scope_is_rejected_by_the_matcher(llm_factory) -> None:
    llm, _, _, _ = llm_factory([_extraction("p4", second_scope="globex")], mode="live")
    try:
        result = await Brain(llm).analyze_pair(_pair("p4"))
    finally:
        await llm.aclose()
    assert result.predicted == "unrelated"
    assert "different scope" in result.reason


async def test_low_confidence_contradiction_is_not_raised(llm_factory) -> None:
    llm, _, _, _ = llm_factory(
        [_extraction("p5"), _classification("contradiction", confidence=0.4)], mode="live"
    )
    try:
        result = await Brain(llm).analyze_pair(_pair("p5"))
    finally:
        await llm.aclose()
    assert result.predicted == "compatible"
    assert result.candidate is False
    assert result.relation == "contradiction"


async def test_hypothetical_extracts_no_claim_and_is_silent(llm_factory) -> None:
    empty = {
        "results": [
            {"message_id": "p6-a", "claims": []},
            {
                "message_id": "p6-b",
                "claims": [_claim("b", "removed from Q4", "negate", "*")],
            },
        ]
    }
    llm, transport, _, _ = llm_factory([empty], mode="live")
    try:
        result = await Brain(llm).analyze_pair(_pair("p6"))
    finally:
        await llm.aclose()
    assert result.predicted == "unrelated"
    assert result.stage == "extraction"
    assert len(transport.calls) == 1


async def test_prefilter_drops_chatter_before_any_model_call(llm_factory) -> None:
    pair = EvalPair(
        id="p7",
        a=EvalSide(
            room="sales", author="maria", text="Happy birthday everyone, great work this week!"
        ),
        b=EvalSide(
            room="engineering", author="tomas", text="We are pulling SSO out of Q4 this morning."
        ),
        label=Relation.UNRELATED,
    )
    llm, transport, _, _ = llm_factory([], mode="live")
    try:
        result = await Brain(llm).analyze_pair(pair)
    finally:
        await llm.aclose()
    assert result.predicted == "unrelated"
    assert result.stage == "prefilter"
    assert transport.calls == []
