"""Wire contract: tolerant candidate packets, strict sender/layout checks."""

from __future__ import annotations

from splitbrain.core.packets import encode
from splitbrain.core.protocol import (
    CandidatePacket,
    ConsentPacket,
    DecidedPacket,
    PacketClaim,
    read_packet,
    validate,
)


def claim(*, private: bool = False) -> dict[str, object]:
    return {
        "id": "clm_1",
        "room_id": "room-1",
        "room_name": "engineering",
        "channel_type": "channel_private" if private else "channel_public",
        "message_id": "sw_1",
        "thread_id": None,
        "author": "tomas",
        "text": None if private else "SSO ships on December 1.",
        "text_withheld": private,
        "subject": "SSO",
        "subject_key": "sso",
        "scope": "Acme",
        "scope_key": "acme",
        "value": "December 1",
    }


def candidate() -> dict[str, object]:
    return {
        "id": "sb-0001",
        "claim_a": claim(),
        "claim_b": claim(private=True),
        "confidence": 0.91,
        "reason": "Two dates.",
        "created_at": "2026-11-04T10:00:00+00:00",
    }


def test_candidate_with_a_withheld_quote_validates() -> None:
    payload = validate("candidate", candidate())
    assert isinstance(payload, CandidatePacket)
    assert payload.claim_b.text is None
    assert payload.claim_b.text_withheld is True
    assert payload.claim_a.text == "SSO ships on December 1."
    assert payload.claim_b.thread_root == "sw_1"
    assert payload.claim_b.origin_label == "origin: #engineering (tomas)"


def test_candidate_from_wire_line_is_accepted_only_from_our_agents() -> None:
    body = "Possible contradiction.\n" + encode("candidate", candidate())
    assert read_packet(body, "splitbrain-sentinel") is not None
    assert read_packet(body, "maria") is None
    assert read_packet(body, "splitbrain-arbiter-b")[0] == "candidate"


def test_bad_payloads_are_logged_and_ignored() -> None:
    assert validate("candidate", {"id": "sb-1"}) is None
    assert validate("no_such_kind", {"a": 1}) is None
    body = "hello\n" + encode("candidate", {"id": "sb-1"})
    assert read_packet(body, "splitbrain-sentinel") is None


def test_extra_wire_fields_are_tolerated() -> None:
    data = candidate()
    data["future_field"] = "ok"
    assert isinstance(validate("candidate", data), CandidatePacket)
    assert isinstance(PacketClaim.model_validate(claim(private=True)), PacketClaim)


def test_consent_carries_the_literal_text_only_when_granted() -> None:
    granted = ConsentPacket(
        candidate_id="sb-0001",
        claim_id="clm_2",
        author="tomas",
        granted=True,
        text="We're pulling SSO out of Q4.",
    )
    denied = ConsentPacket(candidate_id="sb-0001", claim_id="clm_2", author="tomas", granted=False)
    assert granted.text and denied.text is None


def test_decided_packet_requires_a_full_decision() -> None:
    assert validate("decided", {"candidate_id": "sb-1"}) is None
    assert isinstance(
        validate(
            "decided",
            {
                "candidate_id": "sb-1",
                "decision": {
                    "candidate_id": "sb-1",
                    "room_id": "r",
                    "text": "SSO in Q1",
                    "proposed_by": "maria",
                    "confirmed_by": "tomas",
                    "decided_at": "2026-11-04T10:00:00+00:00",
                },
                "conflict_room": "r",
                "conflict_room_name": "conflict-sb-1-sso",
                "origins": [],
                "subject": "SSO",
                "authors": ["maria", "tomas"],
            },
        ),
        DecidedPacket,
    )
