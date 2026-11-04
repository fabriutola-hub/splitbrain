"""M5 Verifier: the evidence reply is readable and ends with one packet line."""

from __future__ import annotations

from splitbrain.agents.verifier import Verifier
from splitbrain.core.models import Evidence, EvidenceItem
from splitbrain.core.packets import decode
from splitbrain.core.protocol import EvidenceClaim, EvidenceRequestPacket

REQUEST = EvidenceRequestPacket(
    candidate_id="sb-0001",
    subject="SSO",
    subject_key="sso",
    scope="Acme",
    claim_a=EvidenceClaim(room="sales", value="December 1", date="2026-12-01"),
    claim_b=EvidenceClaim(room="engineering", value="removed from Q4", date=None),
)
EVIDENCE = Evidence(
    candidate_id="sb-0001",
    source="fixture",
    status="supports_b",
    items=[
        EvidenceItem(
            title="#2 SSO (SAML / OIDC) for enterprise customers",
            url="https://github.com/fabriutola-hub/splitbrain-demo-roadmap/issues/2",
            state="open",
            milestone="Q1 2027",
            labels=["enhancement"],
            updated_at="2026-11-04T07:43:35Z",
        )
    ],
    summary="issue #2 moved from Q4 2026 to Q1 2027 on Nov 4",
)


def test_evidence_reply_ends_with_one_packet_line() -> None:
    body = Verifier._body(REQUEST, EVIDENCE)
    lines = body.splitlines()
    assert lines[-1].startswith("sb:evidence ")
    kind, data = decode(lines[-1])
    assert kind == "evidence"
    assert data["candidate_id"] == "sb-0001"
    assert data["source"] == "fixture"
    assert sum(line.startswith("sb:") for line in lines) == 1
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in body
    assert "not a decision about who is right" in body
    assert "|" not in body  # plain text, no Markdown tables
