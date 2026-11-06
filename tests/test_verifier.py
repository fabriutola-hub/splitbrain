"""Verifier: the evidence reply is readable and ends with one packet line."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from splitbrain import bootstrap
from splitbrain.agents.verifier import Verifier
from splitbrain.core.models import Evidence, EvidenceItem
from splitbrain.core.packets import decode, encode
from splitbrain.core.protocol import EvidenceClaim, EvidenceRequestPacket
from splitbrain.evidence.github import (
    EvidenceSettings,
    GitHubEvidence,
    GitHubIssue,
    GitHubSnapshot,
    MilestoneEvent,
    SplitbrainEvidenceError,
    TransientEvidenceError,
)
from splitbrain.switch.events import MessageFrame, MessagePayload

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


REPO = "https://github.com/fabriutola-hub/splitbrain-demo-roadmap"
CLAIM_A = EvidenceClaim(room="sales", value="live on 2026-12-01", date="2026-12-01")
CLAIM_B = EvidenceClaim(room="engineering", value="removed from Q4 delivery", date=None)


def sso_snapshot() -> GitHubSnapshot:
    return GitHubSnapshot(
        repo=REPO,
        issues=[
            GitHubIssue(
                number=2,
                title="SSO (SAML / OIDC) for enterprise customers",
                body="Single sign-on for enterprise workspaces.",
                url=f"{REPO}/issues/2",
                state="open",
                milestone="Q1 2027",
                timeline=[
                    MilestoneEvent(
                        event="milestoned",
                        milestone="Q4 2026",
                        created_at="2026-11-04T07:42:26Z",
                    ),
                    MilestoneEvent(
                        event="demilestoned",
                        milestone="Q4 2026",
                        created_at="2026-11-04T07:43:18Z",
                    ),
                    MilestoneEvent(
                        event="milestoned",
                        milestone="Q1 2027",
                        created_at="2026-11-04T07:43:18Z",
                    ),
                ],
            )
        ],
    )


class FakeProvider:
    slug = "fabriutola-hub/splitbrain-demo-roadmap"

    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.calls = 0

    async def snapshot_any(self, terms: list[str]) -> tuple[GitHubSnapshot, str]:
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result  # type: ignore[return-value]


def make_verifier(
    *,
    retry_attempts: int = 3,
    retry_backoff_s: float = 0.05,
    sleep=None,
) -> Verifier:
    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    return Verifier(
        agent=object(),  # type: ignore[arg-type]
        state=state,
        evidence_settings=EvidenceSettings(mode="live", fixture_path=Path("unused.json")),
        retry_attempts=retry_attempts,
        retry_backoff_s=retry_backoff_s,
        sleep=sleep or (lambda _: asyncio.sleep(0)),
    )


async def test_github_timeout_twice_then_ok_returns_normal_evidence() -> None:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    verifier = make_verifier(retry_backoff_s=0.05, sleep=fake_sleep)
    provider = FakeProvider(
        [
            TransientEvidenceError("timeout 1"),
            TransientEvidenceError("timeout 2"),
            (sso_snapshot(), "SSO"),
        ]
    )
    verifier.provider = provider  # type: ignore[assignment]
    evidence = await verifier._github_evidence(
        "sb-0001", "SSO", "sso", claim_a=CLAIM_A, claim_b=CLAIM_B
    )
    assert provider.calls == 3
    assert delays == [0.05, 0.1]
    assert evidence.status == "supports_b"
    assert evidence.summary.startswith("Supports B: ")
    assert "moved from Q4 2026 to Q1 2027" in evidence.summary


async def test_github_timeout_three_times_returns_unavailable_without_raising() -> None:
    verifier = make_verifier(retry_backoff_s=0.0)
    provider = FakeProvider([TransientEvidenceError("timeout")] * 3)
    verifier.provider = provider  # type: ignore[assignment]
    evidence = await verifier._github_evidence(
        "sb-0001", "SSO", "sso", claim_a=CLAIM_A, claim_b=CLAIM_B
    )
    assert provider.calls == 3
    assert evidence.status == "unavailable"
    assert evidence.summary == "Evidence unavailable: GitHub did not respond after 3 attempts."
    assert evidence.source == "github"
    assert evidence.items == []
    assert "timeout" in evidence.detail


async def test_non_transient_github_error_fails_loudly_without_retrying() -> None:
    verifier = make_verifier()
    provider = FakeProvider([SplitbrainEvidenceError("HTTP 404: Not Found")])
    verifier.provider = provider  # type: ignore[assignment]
    with pytest.raises(SplitbrainEvidenceError, match="HTTP 404"):
        await verifier._github_evidence("sb-0001", "SSO", "sso", claim_a=CLAIM_A, claim_b=CLAIM_B)
    assert provider.calls == 1


@respx.mock
async def test_github_404_is_not_retried_by_the_verifier() -> None:
    route = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    verifier = make_verifier()
    provider = GitHubEvidence(EvidenceSettings(mode="live", fixture_path=Path("unused.json")), REPO)
    verifier.provider = provider
    try:
        with pytest.raises(SplitbrainEvidenceError, match="HTTP 404") as error:
            await verifier._github_evidence(
                "sb-0001", "SSO", "sso", claim_a=CLAIM_A, claim_b=CLAIM_B
            )
    finally:
        await provider.aclose()
    assert not isinstance(error.value, TransientEvidenceError)
    assert route.call_count == 1


async def test_unavailable_evidence_is_posted_to_the_arbiter_without_crashing() -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.targeted_calls: list[dict] = []

        async def targeted(self, room_id: str, body: str, **kwargs) -> dict:
            self.targeted_calls.append({"room_id": room_id, "body": body, **kwargs})
            return {}

    verifier = make_verifier(retry_backoff_s=0.0)
    fake = FakeAgent()
    verifier.agent = fake  # type: ignore[assignment]
    verifier.provider = FakeProvider([TransientEvidenceError("timeout")] * 3)  # type: ignore[assignment]
    frame = MessageFrame(
        kind="message",
        sequence=1,
        room_id="r-ops",
        payload=MessagePayload(
            message_id="sw_req",
            sender_name="splitbrain-arbiter",
            body="Evidence request.\n" + encode("evidence_request", REQUEST),
            thread_id="sw-root",
        ),
    )
    await verifier._on_message(frame)
    assert len(fake.targeted_calls) == 1
    call = fake.targeted_calls[0]
    assert call["target_roles"] == ["arbiter"]
    assert call["thread_id"] == "sw-root"
    kind, payload = decode(call["body"].splitlines()[-1])
    assert kind == "evidence"
    assert payload["status"] == "unavailable"
    assert payload["summary"] == "Evidence unavailable: GitHub did not respond after 3 attempts."
    assert "sb-0001" in verifier.answered
