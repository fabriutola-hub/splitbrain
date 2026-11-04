"""Semantic extraction cache: one model call per unique message body."""

from __future__ import annotations

from splitbrain.core.extractor import Extractor
from splitbrain.core.models import Message


def message(identifier: str, text: str, *, room: str = "sales") -> Message:
    return Message(
        message_id=identifier,
        room_id=room,
        room_name=room,
        author="maria",
        text=text,
    )


def reply(ids: list[str]) -> dict:
    return {
        "results": [
            {
                "message_id": identifier,
                "claims": [
                    {
                        "kind": "commitment",
                        "subject": "SSO",
                        "subject_key": "sso",
                        "scope": "Acme",
                        "scope_key": "acme",
                        "value": "live on December 1",
                        "polarity": "affirm",
                        "effective_date": None,
                        "confidence": 0.9,
                    }
                ],
            }
            for identifier in ids
        ]
    }


async def test_repeated_message_body_is_extracted_once(llm_factory) -> None:
    llm, transport, _, _ = llm_factory([reply(["a1", "b1"])], mode="live")
    extractor = Extractor(llm)
    try:
        first = await extractor.extract_batch(
            [message("a1", "SSO ships December 1."), message("b1", "SSO is delayed to Q1.")]
        )
        second = await extractor.extract_batch(
            [
                message("a2", "SSO ships December 1.", room="engineering"),
                message("b2", "SSO is delayed to Q1."),
            ]
        )
    finally:
        await llm.aclose()
    assert len(transport.calls) == 1
    assert first["a1"][0].subject_key == second["a2"][0].subject_key == "sso"
    assert second["a2"][0].room_name == "engineering"
    assert second["a2"][0].id != first["a1"][0].id


async def test_replay_reads_each_cassette_once(llm_factory) -> None:
    record_llm, _, _, _ = llm_factory([reply(["a1"])], mode="record")
    try:
        await Extractor(record_llm).extract_batch([message("a1", "SSO ships December 1.")])
    finally:
        await record_llm.aclose()

    replay_llm, transport, _, _ = llm_factory([], mode="replay")
    extractor = Extractor(replay_llm)
    try:
        await extractor.extract_batch([message("a1", "SSO ships December 1.")])
        await extractor.extract_batch([message("a2", "SSO ships December 1.")])
    finally:
        await replay_llm.aclose()
    assert transport.calls == []
