"""Render `docs/assets/screens/sentinel-tui.svg` from the real Sentinel TUI.

Reproducible command:

    uv run python scripts/render_tui_svg.py

Uses the same deterministic SSO cycle data as `tests/test_tui.py` and
`tests/tui_snapshot_120x32.txt`, rendered in colour at 120x32 with rich's
`Console(record=True, width=120)` and `export_svg`.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from splitbrain.tui import HEIGHT, WIDTH, CandidateLink, ClaimView, SentinelTui  # noqa: E402

OUTPUT = ROOT / "docs" / "assets" / "screens" / "sentinel-tui.svg"
TITLE = "uv run splitbrain run sentinel --tui"


def build_sso_view(*, width: int = WIDTH, height: int = HEIGHT) -> SentinelTui:
    llm = SimpleNamespace(mode="replay", model="deepseek-ai/DeepSeek-V4.1-Flash-1017")
    view = SentinelTui(llm, width=width, height=height)  # type: ignore[arg-type]
    for _ in range(14):
        view.add_internal()
    view.add_message(
        "sales",
        "maria",
        "Morning! Big one: confirmed with Acme that SSO will be live for them on December 1.",
        True,
        "signal",
        at="23:18",
    )
    view.add_message(
        "support",
        "lucia",
        "Reminder: the support desk closes at 6 pm this week while half the team "
        "is at the offsite.",
        False,
        "pure chatter",
        at="23:18",
    )
    view.add_message(
        "engineering",
        "tomas",
        "Heads up: we're pulling SSO out of Q4. The auth migration has to land first.",
        True,
        "signal",
        at="23:18",
    )
    view.add_message(
        "finance", "pablo", "Q4 budget review moved to Thursday.", True, "signal", at="23:18"
    )
    view.add_message("engineering", "tomas", "yes", True, "consent answer", at="23:19")
    view.add_candidate(
        CandidateLink(
            candidate_id="sb-8510",
            a=ClaimView("sales", "maria", "SSO", "Acme", "live on December 1", "clm_1"),
            b=ClaimView("engineering", "tomas", "SSO", "*", "removed from Q4", "clm_2"),
            confidence=0.94,
            reason="Two different delivery dates.",
        )
    )
    steps = (
        ("candidate", "candidate sent (SSO for Acme)", "23:18:41"),
        ("evidence", "evidence: GitHub issue #2 moved Q4 2026 → Q1 2027", "23:18:43"),
        ("verdict", "verdict CONFIRMED", "23:18:44"),
        ("consent_asked", "consent asked @tomas", "23:18:45"),
        ("consent_answer", "consent granted @tomas", "23:18:47"),
        ("room", "room #conflict-sb-8510-sso", "23:18:49"),
        ("decided", 'DECIDED "SSO beta for Acme on December 15, GA in Q1."', "23:19:12"),
        ("corrections", "corrections posted in #sales, #engineering", "23:19:13"),
    )
    for key, text, at in steps:
        view.add_step("sb-8510", key, text, at=at)
    view.add_log("Extracted 1 claim(s) from #sales: sso/acme=December 1")
    view.add_log("No alert: compatible (confidence 0.90): two phases of one rollout")
    view.add_log("Corrections posted in #sales, #engineering for sb-8510")
    return view


def render_svg(destination: Path = OUTPUT) -> Path:
    view = build_sso_view()
    console = Console(
        record=True,
        width=view.width,
        height=view.height,
        file=StringIO(),
        force_terminal=True,
        color_system="standard",
        legacy_windows=False,
    )
    console.print(view.render())
    svg = console.export_svg(title=TITLE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding="utf-8")
    return destination


def main() -> None:
    path = render_svg()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
