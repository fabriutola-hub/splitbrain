"""M5 evidence: live/fixture modes, milestone moves, fail-loud network errors."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from splitbrain.config import SplitbrainError
from splitbrain.evidence.github import (
    FIXTURE_BANNER,
    EvidenceSettings,
    GitHubEvidence,
    GitHubSnapshot,
    SplitbrainEvidenceError,
    build_evidence,
    milestone_move,
    repo_slug,
)

REPO = "https://github.com/fabriutola-hub/splitbrain-demo-roadmap"
ROOT = Path(__file__).resolve().parents[1]


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
    evidence = build_evidence("sb-0001", "SSO", snapshot, source="fixture")
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
    evidence = build_evidence("sb-0001", "SSO", snapshot, source="github")
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
