"""Record `seed/github_fixture.json` from the real public demo roadmap repo.

Reproducible command (needs internet, no API key required for a public repo):

    uv run python scripts/record_github_fixture.py

The output has exactly the shape `GitHubEvidence.snapshot()` returns in live
mode: all open issues with their milestone timelines. GITHUB_TOKEN is used when
set, to avoid the unauthenticated search rate limit.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from splitbrain.bootstrap import DEFAULT_ROADMAP_REPO  # noqa: E402
from splitbrain.config import Paths, SplitbrainError  # noqa: E402
from splitbrain.evidence.github import EVIDENCE_MODES, EvidenceSettings, GitHubEvidence  # noqa: E402


async def main() -> None:
    paths = Paths.default()
    local = dotenv_values(paths.root / ".env.local")
    repo = (
        os.environ.get("SPLITBRAIN_ROADMAP_REPO")
        or local.get("SPLITBRAIN_ROADMAP_REPO")
        or DEFAULT_ROADMAP_REPO
    )
    mode = os.environ.get("SPLITBRAIN_EVIDENCE_MODE", "live")
    if mode not in EVIDENCE_MODES:
        raise SplitbrainError(f"SPLITBRAIN_EVIDENCE_MODE must be one of {EVIDENCE_MODES}")
    settings = EvidenceSettings(
        mode="live", fixture_path=paths.root / "seed" / "github_fixture.json"
    )
    provider = GitHubEvidence(settings, str(repo))
    try:
        snapshot = await provider.capture()
    finally:
        await provider.aclose()
    print(f"Recorded {len(snapshot.issues)} open issues from {repo}")
    for issue in snapshot.issues:
        print(f"  #{issue.number} {issue.title} (milestone {issue.milestone or 'none'})")
    print(f"Wrote {settings.fixture_path}")


if __name__ == "__main__":
    asyncio.run(main())
