"""Explicit, opt-in evidence for the hackathon closing-beat scenario.

The demo roadmap repo has no issue about the hackathon prize pages, so a live or
fixture GitHub lookup would honestly return "no evidence" and the Arbiter would
discard the case. Rather than invent a GitHub issue, this module reads a
committed, clearly labelled scenario fixture: paraphrases of the two *public*
announcement pages. It is enabled only when SPLITBRAIN_SCENARIO_EVIDENCE names
the scenario (`splitbrain demo --scenario hackathon` sets it), announces itself
with a [DEGRADED] banner, and never pretends to be GitHub data.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..config import Paths, SplitbrainError
from ..core.models import Evidence, EvidenceItem

ENV_VAR = "SPLITBRAIN_SCENARIO_EVIDENCE"
FIXTURE_RELATIVE_PATH = Path("seed") / "scenario_evidence.json"
BANNER_PREFIX = "[DEGRADED] EVIDENCE: scenario fixture"


class ScenarioFixtureEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    keywords: list[str] = Field(default_factory=list)
    summary: str
    detail: str
    items: list[EvidenceItem] = Field(default_factory=list)


class ScenarioFixtureFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str
    scenarios: dict[str, ScenarioFixtureEntry]


@dataclass(frozen=True, slots=True)
class ScenarioEvidence:
    name: str
    label: str
    keywords: tuple[str, ...]
    summary: str
    detail: str
    items: tuple[EvidenceItem, ...]

    def banner(self) -> str:
        return f"{BANNER_PREFIX} {self.name!r} ({self.label}); not GitHub data"

    def matches(self, subject: str) -> bool:
        needle = subject.casefold()
        return any(keyword.casefold() in needle for keyword in self.keywords)

    def evidence(self, candidate_id: str) -> Evidence:
        return Evidence(
            candidate_id=candidate_id,
            source="scenario_fixture",
            status="conflicting",
            items=list(self.items),
            summary=self.summary,
            detail=f"{self.label}: {self.detail}",
        )


def enabled_name() -> str | None:
    name = os.environ.get(ENV_VAR, "").strip().lower()
    return name or None


def load_entry(name: str, paths: Paths | None = None) -> ScenarioEvidence:
    """Read one named entry directly; used by the demo to print its banner."""
    resolved = paths or Paths.default()
    path = resolved.root / FIXTURE_RELATIVE_PATH
    if not path.is_file():
        raise SplitbrainError(
            f"{ENV_VAR}={name!r} but {path} is missing. Unset {ENV_VAR} to use "
            "GitHub evidence only."
        )
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        fixture = ScenarioFixtureFile.model_validate(document)
    except (ValueError, OSError) as exc:
        raise SplitbrainError(f"Cannot read the scenario evidence fixture {path}: {exc}") from exc
    entry = fixture.scenarios.get(name)
    if entry is None:
        raise SplitbrainError(
            f"{ENV_VAR}={name!r} has no entry in {path} "
            f"(available: {', '.join(sorted(fixture.scenarios)) or 'none'})."
        )
    return ScenarioEvidence(
        name=name,
        label=entry.label,
        keywords=tuple(entry.keywords),
        summary=entry.summary,
        detail=entry.detail,
        items=tuple(entry.items),
    )


def load_scenario_evidence(paths: Paths | None = None) -> ScenarioEvidence | None:
    """None when not enabled; fail loud on a bad name or a bad fixture file."""
    name = enabled_name()
    return load_entry(name, paths) if name is not None else None
