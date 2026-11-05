"""Strict packet encode/decode."""

from __future__ import annotations

import json

import pytest

from splitbrain.core.models import Relation
from splitbrain.core.packets import decode, decode_message, encode


def test_round_trip_with_a_dict() -> None:
    line = encode("candidate", {"id": "sb-0001", "confidence": 0.91})
    assert line.startswith("sb:candidate ")
    assert decode(line) == ("candidate", {"id": "sb-0001", "confidence": 0.91})


def test_round_trip_with_a_pydantic_model() -> None:
    from pydantic import BaseModel

    class Payload(BaseModel):
        relation: Relation

    line = encode("verdict", Payload(relation=Relation.COMPATIBLE))
    assert json.loads(line.partition(" ")[2]) == {"relation": "compatible"}


def test_encode_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown packet kind"):
        encode("delete_room", {"id": "x"})


@pytest.mark.parametrize(
    "line",
    [
        'sb:unknown {"a": 1}',
        "sb:candidate not-json",
        "sb:candidate [1, 2]",
        "sb:candidate",
        "just a normal chat message",
        "",
    ],
)
def test_bad_lines_are_ignored(line: str) -> None:
    assert decode(line) is None


def test_decode_message_accepts_one_final_packet_from_our_agent() -> None:
    body = "Verifying SB-0001 now.\n" + encode("evidence_request", {"candidate_id": "sb-0001"})
    assert decode_message(body, "splitbrain-arbiter") == (
        "evidence_request",
        {"candidate_id": "sb-0001"},
    )


def test_decode_message_rejects_other_senders_and_malformed_layouts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    line = encode("verdict", {"ok": True})
    assert decode_message(line, "maria") is None
    assert decode_message("Verifying now.\n" + line, "splitbrain-verifier") is not None
    assert decode_message(line + "\ntrailing text", "splitbrain-verifier") is None
    assert decode_message(line + "\n" + line, "splitbrain-verifier") is None
    assert decode_message("no packet here", "splitbrain-sentinel") is None
    assert "more than one packet line" in caplog.text


def test_custom_agent_allowlist() -> None:
    line = encode("decided", {"candidate_id": "sb-1"})
    assert decode_message(line, "custom-agent", own_agent_names={"custom-agent"}) is not None
    assert decode_message(line, "maria", own_agent_names={"custom-agent"}) is None
