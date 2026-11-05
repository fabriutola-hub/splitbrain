"""GitHub REST evidence: live mode and a committed, reproducible fixture.

The repo URL comes from the GitHub reference attached to `splitbrain-ops` (see
`connect_to_room(ops).references`), never from a chat message. Live mode talks
to the internet with httpx's default `trust_env` so proxy settings are honoured;
a network error fails loudly instead of silently falling back to the fixture.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

from ..config import Paths, SplitbrainError, internet_client
from ..core.models import Evidence, EvidenceItem

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
EVIDENCE_MODES = ("live", "fixture")
FIXTURE_RELATIVE_PATH = Path("seed") / "github_fixture.json"
FIXTURE_BANNER = "[DEGRADED] EVIDENCE: fixture (recorded GitHub data, no network)"


class SplitbrainEvidenceError(SplitbrainError):
    """Live evidence failed; no silent fallback to the fixture was used."""


@dataclass(frozen=True, slots=True)
class EvidenceSettings:
    mode: str
    fixture_path: Path

    @classmethod
    def load(cls, paths: Paths | None = None) -> EvidenceSettings:
        resolved = paths or Paths.default()
        local_file = resolved.root / ".env.local"
        local = dotenv_values(local_file) if local_file.is_file() else {}
        raw = (
            os.environ.get("SPLITBRAIN_EVIDENCE_MODE")
            or local.get("SPLITBRAIN_EVIDENCE_MODE")
            or "live"
        )
        mode = str(raw).strip().lower()
        if mode not in EVIDENCE_MODES:
            raise SplitbrainError(
                f"SPLITBRAIN_EVIDENCE_MODE must be one of {', '.join(EVIDENCE_MODES)}, "
                f"got {mode!r}."
            )
        return cls(mode=mode, fixture_path=resolved.root / FIXTURE_RELATIVE_PATH)

    def banner(self, repo: str) -> str:
        if self.mode == "fixture":
            return FIXTURE_BANNER
        return f"EVIDENCE: live (GitHub REST, {repo})"


class MilestoneEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str
    milestone: str = ""
    created_at: str = ""
    actor: str = ""


class GitHubIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    number: int
    title: str
    body: str = ""
    url: str = ""
    state: str = "open"
    milestone: str = ""
    labels: list[str] = Field(default_factory=list)
    updated_at: str = ""
    timeline: list[MilestoneEvent] = Field(default_factory=list)


class GitHubSnapshot(BaseModel):
    """Exactly the shape the live provider returns; the fixture stores the same."""

    model_config = ConfigDict(extra="allow")

    repo: str
    captured_at: str = ""
    issues: list[GitHubIssue] = Field(default_factory=list)


def repo_slug(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.casefold() not in ("github.com", "www.github.com") or len(parts) < 2:
        raise SplitbrainEvidenceError(
            f"GitHub reference is not a public github.com repository URL: {repo_url!r}"
        )
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def short_date(iso: str) -> str:
    try:
        moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "an unknown date"
    utc = moment.astimezone(UTC)
    return f"{utc.strftime('%b')} {utc.day}"


def milestone_move(issue: GitHubIssue) -> tuple[str, str, str] | None:
    """Return (from, to, short date) when an issue's milestone really changed."""
    events = [item for item in issue.timeline if item.event in ("milestoned", "demilestoned")]
    milestones = [item.milestone for item in events if item.event == "milestoned"]
    if len(milestones) < 2 or milestones[0] == milestones[-1]:
        return None
    last = next(
        (item for item in reversed(events) if item.event == "milestoned" and item.milestone),
        None,
    )
    return milestones[0], milestones[-1], short_date(last.created_at if last else "")


def timeline_text(issue: GitHubIssue) -> str:
    events = [item for item in issue.timeline if item.event in ("milestoned", "demilestoned")]
    return (
        " -> ".join(f"{item.event} {item.milestone}".strip() for item in events)
        or "no milestone events"
    )


class GitHubEvidence:
    """One provider per Verifier process; either live HTTP or the committed fixture."""

    def __init__(
        self,
        settings: EvidenceSettings,
        repo_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        token: str | None = None,
    ) -> None:
        self.settings = settings
        self.repo_url = repo_url
        self.slug = repo_slug(repo_url)
        self._owns_client = client is None
        self._client = client or internet_client(timeout=httpx.Timeout(20.0))
        self._token = (os.environ.get("GITHUB_TOKEN", "") if token is None else token).strip()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{API_ROOT}{path}"
        try:
            response = await self._client.get(url, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SplitbrainEvidenceError(
                f"Live GitHub evidence failed for {self.repo_url} at {path} "
                f"({type(exc).__name__}: {exc}). The evidence request was NOT answered "
                "with a silent fixture fallback. Fix the network/GitHub access, or set "
                "SPLITBRAIN_EVIDENCE_MODE=fixture explicitly to use the recorded data."
            ) from exc
        if response.status_code != 200:
            raise SplitbrainEvidenceError(
                f"Live GitHub evidence failed for {self.repo_url}: GET {path} returned "
                f"HTTP {response.status_code}: {response.text[:300]}. No fixture fallback "
                "was used. Set SPLITBRAIN_EVIDENCE_MODE=fixture explicitly to use recorded data."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise SplitbrainEvidenceError(
                f"Live GitHub evidence failed for {self.repo_url}: GET {path} returned "
                "a non-JSON body. No fixture fallback was used."
            ) from exc

    @staticmethod
    def _issue(item: dict[str, Any], timeline: list[MilestoneEvent]) -> GitHubIssue:
        return GitHubIssue(
            number=int(item["number"]),
            title=str(item.get("title") or ""),
            body=str(item.get("body") or ""),
            url=str(item.get("html_url") or ""),
            state=str(item.get("state") or "open"),
            milestone=str((item.get("milestone") or {}).get("title") or ""),
            labels=[str(label["name"]) for label in item.get("labels") or [] if "name" in label],
            updated_at=str(item.get("updated_at") or ""),
            timeline=timeline,
        )

    async def _timeline(self, number: int) -> list[MilestoneEvent]:
        raw = await self._get(f"/repos/{self.slug}/issues/{number}/timeline")
        if not isinstance(raw, list):
            raise SplitbrainEvidenceError(
                f"Live GitHub timeline for issue #{number} was not a JSON list. "
                "No fixture fallback was used."
            )
        return [
            MilestoneEvent(
                event=str(item.get("event") or ""),
                milestone=str((item.get("milestone") or {}).get("title") or ""),
                created_at=str(item.get("created_at") or ""),
                actor=str((item.get("actor") or {}).get("login") or ""),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    async def _live_snapshot(self, subject: str | None) -> GitHubSnapshot:
        if subject:
            query = f"repo:{self.slug} {subject} in:title,body"
            found = await self._get("/search/issues", {"q": query})
            items = found.get("items", []) if isinstance(found, dict) else []
            if not isinstance(items, list):
                raise SplitbrainEvidenceError("GitHub /search/issues returned no items list")
        else:
            found = await self._get(
                f"/repos/{self.slug}/issues", {"state": "open", "per_page": "100"}
            )
            items = found if isinstance(found, list) else []
        issues: list[GitHubIssue] = []
        for item in items:
            if (
                not isinstance(item, dict)
                or item.get("pull_request")
                or item.get("state") != "open"
            ):
                continue
            # Search results can include closed issues; ignore them.
            timeline = await self._timeline(int(item["number"]))
            issues.append(self._issue(item, timeline))
        return GitHubSnapshot(
            repo=self.repo_url,
            captured_at=datetime.now(UTC).isoformat(timespec="seconds"),
            issues=issues,
        )

    def _fixture_snapshot(self, subject: str | None) -> GitHubSnapshot:
        path = self.settings.fixture_path
        if not path.is_file():
            raise SplitbrainEvidenceError(
                f"Fixture evidence requested but {path} is missing. Run "
                "'uv run python scripts/record_github_fixture.py' against the live repo."
            )
        try:
            snapshot = GitHubSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            raise SplitbrainEvidenceError(f"Cannot read the GitHub fixture {path}: {exc}") from exc
        if subject:
            needle = subject.casefold()
            snapshot = snapshot.model_copy(
                update={
                    "issues": [
                        issue
                        for issue in snapshot.issues
                        if issue.state == "open"
                        and needle in f"{issue.title} {issue.body}".casefold()
                    ]
                }
            )
        return snapshot

    async def snapshot(self, subject: str) -> GitHubSnapshot:
        if self.settings.mode == "fixture":
            return self._fixture_snapshot(subject)
        return await self._live_snapshot(subject)

    async def snapshot_any(self, terms: Sequence[str]) -> tuple[GitHubSnapshot, str]:
        """Try the extracted subject, then its canonical key and its words.

        A model may return a descriptive subject ("refund approval threshold")
        that is not a literal phrase in any issue; its subject_key ("refunds")
        is the searchable term. The first term with issues wins, and the matched
        term is returned so the evidence text names what was really searched.
        """
        words = [term for term in terms if term and term.strip()]
        if not words:
            raise SplitbrainEvidenceError("No evidence search term was supplied")
        tried: set[str] = set()
        last: GitHubSnapshot | None = None
        matched = words[0]
        for term in words:
            key = term.strip().casefold()
            if key in tried:
                continue
            tried.add(key)
            last = await self.snapshot(term)
            matched = term
            if last.issues:
                break
        assert last is not None
        return last, matched

    async def capture(self, destination: Path | None = None) -> GitHubSnapshot:
        """Record every open issue plus its milestone timeline from the live repo."""
        if self.settings.mode != "live":
            raise SplitbrainEvidenceError(
                "Recording the GitHub fixture requires SPLITBRAIN_EVIDENCE_MODE=live."
            )
        snapshot = await self._live_snapshot(None)
        target = destination or self.settings.fixture_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return snapshot


def build_evidence(
    candidate_id: str,
    subject: str,
    snapshot: GitHubSnapshot,
    *,
    source: Literal["github", "fixture"],
) -> Evidence:
    """Turn the provider's output into an Evidence packet."""
    open_issues = [issue for issue in snapshot.issues if issue.state == "open"]
    items = [
        EvidenceItem(
            title=f"#{issue.number} {issue.title}",
            url=issue.url,
            state=issue.state,
            milestone=issue.milestone,
            labels=list(issue.labels),
            updated_at=issue.updated_at,
        )
        for issue in open_issues
    ]
    slug = repo_slug(snapshot.repo)
    tail = f"{len(open_issues)} open issue(s) matched; closed duplicates ignored."
    moves = [(issue, move) for issue in open_issues if (move := milestone_move(issue))]
    if moves:
        issue, (before, after, day) = moves[0]
        # The brief shows only this one sentence; the timeline is for the record.
        summary = f'issue #{issue.number} "{issue.title}" moved from {before} to {after} on {day}.'
        detail = f"GitHub, {slug}: {summary} Timeline: {timeline_text(issue)}. {tail}"
        status = "supports_b"
    elif open_issues:
        issue = open_issues[0]
        milestone = f", milestone {issue.milestone}" if issue.milestone else ""
        summary = f'issue #{issue.number} "{issue.title}" is open{milestone}.'
        detail = (
            f"GitHub, {slug}: {summary} "
            f'It is the closest open issue for "{subject}"; no milestone move was recorded. '
            f"{tail}"
        )
        status = "conflicting"
    else:
        summary = f'no open issue mentions "{subject}".'
        detail = f"GitHub, {slug}: {summary} {tail}"
        status = "none"
    return Evidence(
        candidate_id=candidate_id,
        source=source,
        status=status,
        items=items,
        summary=summary,
        detail=detail,
    )
