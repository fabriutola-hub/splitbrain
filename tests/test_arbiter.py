"""M5 Arbiter: verdict rule, consent-aware quotes, brief and decision record."""

from __future__ import annotations

import pytest

from splitbrain import bootstrap
from splitbrain.agents import arbiter as mod
from splitbrain.core.models import Evidence
from splitbrain.core.protocol import CandidatePacket, ConsentPacket, PacketClaim


def packet_claim(*, private: bool, author: str, room: str) -> PacketClaim:
    return PacketClaim(
        id=f"clm_{author}",
        room_id=f"r-{room}",
        room_name=room,
        channel_type="channel_private" if private else "channel_public",
        message_id=f"sw_{author}",
        author=author,
        ts=1793776781000,
        text=None if private else "Confirmed with Acme: SSO live on December 1.",
        text_withheld=private,
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        value="December 1" if not private else "removed from Q4 delivery",
    )


def verification(*, granted: bool | None = None) -> mod.Verification:
    candidate = CandidatePacket(
        id="sb-0001",
        claim_a=packet_claim(private=False, author="maria", room="sales"),
        claim_b=packet_claim(private=True, author="tomas", room="engineering"),
        confidence=0.93,
        reason="Two dates.",
    )
    item = mod.Verification(candidate=candidate, thread_id="sw-root", requested_at=0.0)
    item.evidence = Evidence(
        candidate_id="sb-0001",
        source="github",
        status="supports_b",
        summary="issue #2 moved from Q4 2026 to Q1 2027 on Nov 4",
        items=[],
    )
    item.link_labels = ["origin: #sales (maria)", "origin: #engineering (tomas)"]
    if granted is not None:
        item.consents["clm_tomas"] = ConsentPacket(
            candidate_id="sb-0001",
            claim_id="clm_tomas",
            author="tomas",
            granted=granted,
            text="We're pulling SSO out of Q4. The auth migration has to land first."
            if granted
            else None,
        )
    return item


def make_arbiter() -> mod.Arbiter:
    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    return mod.Arbiter(
        agent=object(),  # type: ignore[arg-type]
        state=state,
        name=mod.AGENT_NAME,
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )


@pytest.mark.parametrize(
    ("confidence", "status", "expected"),
    [
        (0.93, "supports_b", "confirmed"),
        (0.70, "conflicting", "confirmed"),
        (0.69, "supports_b", "discarded"),
        (0.99, "none", "discarded"),
    ],
)
def test_verdict_rule(confidence: float, status: str, expected: str) -> None:
    assert mod.verdict_for(confidence, status) == expected


def test_slug() -> None:
    assert mod._slug("SSO!") == "sso"
    assert mod._slug("") == "subject"


def test_quotes_are_withheld_until_the_author_consents() -> None:
    denied = verification(granted=False)
    assert "(quote withheld at the author's request)" in mod._quote(
        denied.candidate.claim_b, denied.consents
    )
    assert "Subject: SSO" in mod._quote(denied.candidate.claim_b, denied.consents)
    granted = verification(granted=True)
    quote = mod._quote(granted.candidate.claim_b, granted.consents)
    assert "We're pulling SSO out of Q4" in quote
    assert "withheld" not in quote


def test_brief_cites_both_quotes_only_after_consent() -> None:
    arbiter = make_arbiter()
    denied = verification(granted=False)
    brief = arbiter._brief(denied)
    assert "@maria @tomas" in brief
    assert "Confirmed with Acme" in brief
    assert "We're pulling SSO out of Q4" not in brief
    assert "(quote withheld at the author's request)" in brief
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in brief
    assert "decision:" in brief and "confirm" in brief
    granted = verification(granted=True)
    assert "We're pulling SSO out of Q4" in arbiter._brief(granted)


def test_decision_record_is_open_and_contains_evidence_and_origins() -> None:
    arbiter = make_arbiter()
    record = arbiter._open_record(verification(granted=False))
    assert "Status: OPEN" in record
    assert "SB-0001 decision record" in record
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in record
    assert "origin: #sales (maria)" in record
    assert "origin: #engineering (tomas)" in record
    assert "only @maria and @tomas" in record


def test_consent_timeout_fills_missing_answers_as_denied() -> None:
    item = verification()
    item.withheld_ids = {"clm_tomas"}
    mod.Arbiter._fill_missing_consents(item)
    assert item.consents["clm_tomas"].granted is False
    assert item.consents["clm_tomas"].text is None
