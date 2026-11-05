"""Readable Sentinel TUI: people-only inbox, candidate lifecycle, fit to width."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from splitbrain.tui import (
    HEIGHT,
    WIDTH,
    CandidateLink,
    ClaimView,
    IncomingMessage,
    SentinelTui,
)

SNAPSHOT = Path(__file__).with_name("tui_snapshot_120x32.txt")


def _render(view: SentinelTui) -> str:
    console = Console(width=view.width, height=view.height, record=True, file=StringIO())
    console.print(view.render())
    return console.export_text()


def _llm() -> SimpleNamespace:
    return SimpleNamespace(mode="replay", model="deepseek-ai/DeepSeek-V4.1-Flash-1017")


def sso_view(*, width: int = WIDTH, height: int = HEIGHT) -> SentinelTui:
    """A deterministic render of the complete SSO cycle, for the snapshot."""
    view = SentinelTui(_llm(), width=width, height=height)  # type: ignore[arg-type]
    view.add_internal()
    for _ in range(13):
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


def test_snapshot_of_the_whole_sso_cycle() -> None:
    assert _render(sso_view()) == SNAPSHOT.read_text(encoding="utf-8")


def test_full_names_and_untruncated_demo_sentences() -> None:
    output = _render(sso_view())
    assert "INCOMING MESSAGES" in output
    assert "CANDIDATE LIFECYCLE" in output
    assert "#sales" in output and "María Gómez (@maria)" in output
    assert "#engineering" in output and "Tomás Rivera (@tomas)" in output
    assert "SSO will be live" in output and "for them on December 1." in output
    assert "The auth migration" in output and "has to land first." in output
    assert "…" not in output  # no phrase is truncated with an ellipsis
    assert "#splitbra..." not in output
    assert "internal 14" in output
    assert "DeepSeek-V4.1-Flash-1017" in output
    assert "deepseek-ai/DeepSeek" not in output


def test_linked_claims_are_shown_above_the_lifecycle() -> None:
    output = _render(sso_view())
    pair = (
        "#sales María: SSO for Acme = live on December 1",
        "⟷ CONTRADICTION ⟷",
        "#engineering Tomás: SSO = removed from Q4",
    )
    positions = [output.index(line) for line in pair]
    assert positions == sorted(positions)
    assert positions[-1] < output.index("candidate sent")
    assert "CLAIMS + CANDIDATE LINK" not in output


def test_lifecycle_tells_the_whole_story_in_order() -> None:
    output = _render(sso_view())
    markers = (
        "candidate sent",
        "GitHub issue #2 moved Q4",
        "2026 → Q1 2027",
        "verdict CONFIRMED",
        "consent asked @tomas",
        "consent granted @tomas",
        "room #conflict-sb-8510-sso",
        "DECIDED",
        "corrections posted",
    )
    positions = [output.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert "✓" in output
    assert "CLAIMS + CANDIDATE LINK" not in output


def test_no_line_exceeds_the_console_width() -> None:
    for width, height in ((WIDTH, HEIGHT), (100, 30)):
        view = sso_view(width=width, height=height)
        text = _render(view)
        lines = text.splitlines()
        assert len(lines) <= height + 1
        for line in lines:
            assert len(line) <= width, f"{width}x{height}: {len(line)} cells: {line!r}"
        assert "internal 14" in text
        assert "DeepSeek-V4.1-Flash-1017" in text
        assert "││" not in text


def test_only_meaningful_log_events_reach_the_footer() -> None:
    view = SentinelTui()
    handler = view.log_handler()
    for message in (
        "Rooms changed (subscription updated): 1 covered",
        "Claimed room #sales for the event stream",
        "Extracted 1 claim(s) from #sales",
        "No alert: compatible (confidence 0.90)",
        "Corrections posted in #sales, #engineering for sb-8510",
    ):
        handler.handle(logging.LogRecord("x", logging.INFO, "f.py", 1, message, (), None))
    assert list(view.logs) == [
        "Extracted 1 claim(s) from #sales",
        "No alert: compatible (confidence 0.90)",
        "Corrections posted in #sales, #engineering for sb-8510",
    ]


def test_filtered_messages_are_dimmed() -> None:
    lines = SentinelTui._left_lines(
        [IncomingMessage("support", "lucia", "hello there", False, "pure chatter", "23:18")],
        60,
        5,
    )
    assert lines[0][1] == "dim"
