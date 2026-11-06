"""Evidence: live/fixture modes, milestone moves, relevance and fail-loud network errors."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from splitbrain.agents.arbiter import verdict_for
from splitbrain.config import SplitbrainError
from splitbrain.core.protocol import EvidenceClaim
from splitbrain.evidence.github import (
    FIXTURE_BANNER,
    EvidenceSettings,
    GitHubEvidence,
    GitHubIssue,
    GitHubSnapshot,
    SplitbrainEvidenceError,
    build_evidence,
    extract_amounts,
    extract_claim_values,
    extract_date_values,
    extract_quarters,
    issue_is_relevant,
    milestone_move,
    repo_slug,
)

REPO = "https://github.com/fabriutola-hub/splitbrain-demo-roadmap"
ROOT = Path(__file__).resolve().parents[1]

SSO_CLAIM_A = EvidenceClaim(room="sales", value="live on 2026-12-01", date="2026-12-01")
SSO_CLAIM_B = EvidenceClaim(room="engineering", value="removed from Q4 delivery", date=None)
REFUND_CLAIM_A = EvidenceClaim(
    room="support",
    value="refunds above $500 can be approved without manager sign-off",
    date=None,
)
REFUND_CLAIM_B = EvidenceClaim(
    room="finance",
    value="manager approval required above $250",
    date=None,
)


def settings(mode: str = "fixture") -> EvidenceSettings:
    return EvidenceSettings(mode=mode, fixture_path=ROOT / "seed" / "github_fixture.json")


def test_repo_slug_and_rejections() -> None:
    assert repo_slug(REPO) == "fabriutola-hub/splitbrain-demo-roadmap"
    with pytest.raises(SplitbrainEvidenceError, match="not a public github.com"):
        repo_slug("https://example.com/owner/repo")


def test_settings_mode_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPLITBRAIN_EVIDENCE_MODE", "nonsense")
    with pytest.raises(SplitbrainError, match="SPLITBRAIN_EVIDENCE_MODE"):
        EvidenceSettings.load()
    monkeypatch.delenv("SPLITBRAIN_EVIDENCE_MODE")
    assert EvidenceSettings.load().mode == "live"
    assert settings("fixture").banner(REPO) == FIXTURE_BANNER
    assert settings("live").banner(REPO).startswith("EVIDENCE: live")


def test_extract_amounts_percentages_and_units() -> None:
    assert extract_amounts("threshold drops from $500 to $250 or 250 USD") == [
        "$500",
        "$250",
        "250 USD",
    ]
    assert extract_amounts("99.9% uptime SLA and 30 days notice for 20 PRs") == [
        "99.9%",
        "30 days",
        "20 PRs",
    ]
    assert extract_amounts("1000 requests per minute") == ["1000 requests per minute"]


def test_extract_quarters_and_iso_dates() -> None:
    assert extract_quarters("moved from q4 2026 to Q1") == ["Q4 2026", "Q4", "Q1"]
    assert extract_date_values("live on 2026-12-01") == [
        "2026-12-01",
        "December 1",
        "December",
        "Q4 2026",
        "Q4",
    ]
    assert extract_claim_values(SSO_CLAIM_A, SSO_CLAIM_B) == [
        "2026-12-01",
        "December 1",
        "December",
        "Q4 2026",
        "Q4",
    ]


def test_build_evidence_sso_refunds_and_inconclusive_cases() -> None:
    fixture = GitHubSnapshot.model_validate(
        json.loads((ROOT / "seed" / "github_fixture.json").read_text(encoding="utf-8"))
    )

    # 1. SSO: issue #2 moved from Q4 2026 to Q1 2027 and Engineering says "Q4" -> supports_b.
    sso_snapshot = fixture.model_copy(
        update={
            "issues": [
                issue
                for issue in fixture.issues
                if issue.state == "open" and "sso" in f"{issue.title} {issue.body}".casefold()
            ]
        }
    )
    sso_evidence = build_evidence(
        "sb-0001",
        "SSO",
        sso_snapshot,
        source="fixture",
        claim_a=SSO_CLAIM_A,
        claim_b=SSO_CLAIM_B,
    )
    assert sso_evidence.status == "supports_b"
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in sso_evidence.summary
    assert verdict_for(0.95, sso_evidence.status) == "confirmed"

    # 2. Refunds: issue #5 mentions $500 and $250 -> conflicting -> confirmed.
    refunds_snapshot = fixture.model_copy(
        update={
            "issues": [
                issue
                for issue in fixture.issues
                if issue.state == "open" and "refunds" in f"{issue.title} {issue.body}".casefold()
            ]
        }
    )
    refunds_evidence = build_evidence(
        "sb-0002",
        "refunds",
        refunds_snapshot,
        source="fixture",
        claim_a=REFUND_CLAIM_A,
        claim_b=REFUND_CLAIM_B,
    )
    assert refunds_evidence.status == "conflicting"
    assert 'issue #5 "Support macros: refunds over $250' in refunds_evidence.summary
    assert verdict_for(0.92, refunds_evidence.status) == "confirmed"

    # 3. Open issues match the topic, but none mentions any disputed value -> inconclusive.
    unrelated_snapshot = GitHubSnapshot(
        repo=REPO,
        issues=[
            GitHubIssue(
                number=11,
                title="Document SSO terminology",
                body="Explain SAML and OIDC acronyms in the onboarding guide.",
                state="open",
            ),
            GitHubIssue(
                number=12,
                title="Clean up SSO error messages",
                body="Improve user-facing login copy when SAML assertions fail.",
                state="open",
            ),
        ],
    )
    inconclusive = build_evidence(
        "sb-0003",
        "SSO",
        unrelated_snapshot,
        source="fixture",
        claim_a=EvidenceClaim(room="sales", value="$250 or $500", date=None),
        claim_b=EvidenceClaim(room="engineering", value="Q4 or December 1", date=None),
    )
    assert inconclusive.status == "inconclusive"
    assert inconclusive.summary == (
        '2 open issue(s) mention "SSO", but none mentions $250, $500, Q4, December 1 or December.'
    )
    assert verdict_for(0.95, inconclusive.status) == "discarded"


def test_relevance_checks_all_matching_issues_and_picks_the_first_relevant_one() -> None:
    irrelevant = GitHubIssue(
        number=10,
        title="Document refund terminology",
        body="Clarify what a chargeback is in the help centre.",
        state="open",
    )
    relevant = GitHubIssue(
        number=5,
        title="Support macros: refunds over $250 now need manager approval",
        body="Threshold drops from $500 to $250.",
        state="open",
        milestone="Q4 2026",
    )
    values = extract_claim_values(REFUND_CLAIM_A, REFUND_CLAIM_B)
    assert not issue_is_relevant(irrelevant, values)
    assert issue_is_relevant(relevant, values)
    snapshot = GitHubSnapshot(repo=REPO, issues=[irrelevant, relevant])
    evidence = build_evidence(
        "sb-0004",
        "refunds",
        snapshot,
        source="fixture",
        claim_a=REFUND_CLAIM_A,
        claim_b=REFUND_CLAIM_B,
    )
    assert evidence.status == "conflicting"
    assert "issue #5" in evidence.summary


async def test_fixture_filters_by_subject_and_finds_the_milestone_move() -> None:
    provider = GitHubEvidence(settings("fixture"), REPO)
    try:
        snapshot = await provider.snapshot("SSO")
    finally:
        await provider.aclose()
    assert [issue.number for issue in snapshot.issues] == [2, 1]
    move = milestone_move(snapshot.issues[0])
    assert move == ("Q4 2026", "Q1 2027", "Nov 4")
    assert milestone_move(snapshot.issues[1]) is None
    evidence = build_evidence(
        "sb-0001",
        "SSO",
        snapshot,
        source="fixture",
        claim_a=SSO_CLAIM_A,
        claim_b=SSO_CLAIM_B,
    )
    assert evidence.source == "fixture"
    assert evidence.status == "supports_b"
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in evidence.summary
    assert any("#2" in item.title for item in evidence.items)


async def test_fixture_with_no_match_is_none_evidence() -> None:
    provider = GitHubEvidence(settings("fixture"), REPO)
    try:
        snapshot = await provider.snapshot("nonexistent widget")
    finally:
        await provider.aclose()
    evidence = build_evidence("sb-0002", "nonexistent widget", snapshot, source="fixture")
    assert evidence.items == []
    assert evidence.status == "none"


async def test_missing_fixture_fails_loudly(tmp_path: Path) -> None:
    provider = GitHubEvidence(
        EvidenceSettings(mode="fixture", fixture_path=tmp_path / "missing.json"), REPO
    )
    try:
        with pytest.raises(SplitbrainEvidenceError, match="record_github_fixture.py"):
            await provider.snapshot("SSO")
    finally:
        await provider.aclose()


@respx.mock
async def test_live_network_error_fails_with_a_clear_message_and_no_fallback() -> None:
    respx.get("https://api.github.com/search/issues").mock(
        side_effect=httpx.ConnectError("no route to host")
    )
    provider = GitHubEvidence(settings("live"), REPO)
    try:
        with pytest.raises(SplitbrainEvidenceError) as error:
            await provider.snapshot("SSO")
    finally:
        await provider.aclose()
    message = str(error.value)
    assert "Live GitHub evidence failed" in message
    assert "NOT answered" in message
    assert "SPLITBRAIN_EVIDENCE_MODE=fixture" in message
    assert "quietly" not in message.lower()


@respx.mock
async def test_live_non_200_fails_loudly() -> None:
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(403, json={"message": "rate limited"})
    )
    provider = GitHubEvidence(settings("live"), REPO)
    try:
        with pytest.raises(SplitbrainEvidenceError, match="HTTP 403"):
            await provider.snapshot("SSO")
    finally:
        await provider.aclose()


@respx.mock
async def test_live_search_and_timelines_build_the_same_evidence_as_the_fixture() -> None:
    fixture = GitHubSnapshot.model_validate(
        json.loads((ROOT / "seed" / "github_fixture.json").read_text(encoding="utf-8"))
    )
    by_number = {issue.number: issue for issue in fixture.issues}
    items = [
        {
            "number": 2,
            "title": by_number[2].title,
            "body": by_number[2].body,
            "html_url": by_number[2].url,
            "state": "open",
            "milestone": {"title": by_number[2].milestone},
            "labels": [{"name": label} for label in by_number[2].labels],
            "updated_at": by_number[2].updated_at,
        }
    ]
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"total_count": 1, "items": items})
    )
    respx.get(
        "https://api.github.com/repos/fabriutola-hub/splitbrain-demo-roadmap/issues/2/timeline"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "event": event.event,
                    "milestone": {"title": event.milestone},
                    "created_at": event.created_at,
                    "actor": {"login": event.actor},
                }
                for event in by_number[2].timeline
            ],
        )
    )
    provider = GitHubEvidence(settings("live"), REPO)
    try:
        snapshot = await provider.snapshot("SSO")
    finally:
        await provider.aclose()
    evidence = build_evidence(
        "sb-0001",
        "SSO",
        snapshot,
        source="github",
        claim_a=SSO_CLAIM_A,
        claim_b=SSO_CLAIM_B,
    )
    assert evidence.source == "github"
    assert evidence.status == "supports_b"
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in evidence.summary


@respx.mock
async def test_fixture_mode_never_touches_the_network() -> None:
    route = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    provider = GitHubEvidence(settings("fixture"), REPO)
    try:
        await provider.snapshot("SSO")
    finally:
        await provider.aclose()
    assert not route.called
