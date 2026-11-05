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
        "↔ CONTRADICTION ↔",
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


def test_live_uses_the_alternate_screen_and_the_real_terminal_height(
    monkeypatch,
) -> None:
    from io import StringIO

    from rich.console import Console

    import splitbrain.tui as tui_module

    monkeypatch.setattr(tui_module, "terminal_size", lambda: (120, 24))
    view = SentinelTui(_llm())  # type: ignore[arg-type]
    assert (view.width, view.height) == (120, 24)
    assert view._console.height == 24
    view._console = Console(width=120, height=24, force_terminal=True, file=StringIO())
    view.start()
    try:
        assert view._live is not None
        assert view._live._screen is True
    finally:
        view.stop()


def test_render_fits_a_24_row_terminal_without_scrolling() -> None:
    text = _render(sso_view(width=120, height=24))
    assert len(text.splitlines()) <= 24
    assert text.count("SPLITBRAIN SENTINEL | LLM") == 1
    assert "corrections posted in #sales," in text and "#engineering" in text
    assert all(len(line) <= 120 for line in text.splitlines())


def test_evidence_step_shows_the_finding_not_the_repository() -> None:
    from splitbrain.core.models import Evidence
    from splitbrain.tui import evidence_step_text

    evidence = Evidence(
        candidate_id="sb-0001",
        source="github",
        status="supports_b",
        summary=(
            'issue #2 "SSO (SAML / OIDC) for enterprise customers" moved from '
            "Q4 2026 to Q1 2027 on Nov 4."
        ),
        detail=(
            "GitHub, fabriutola-hub/splitbrain-demo-roadmap: issue #2 moved from "
            "Q4 2026 to Q1 2027 on Nov 4. Timeline: milestoned Q4 2026."
        ),
        items=[],
    )
    assert evidence_step_text(evidence) == "GitHub issue #2 moved Q4 2026 → Q1 2027"


def test_room_step_is_stamped_when_the_room_appears() -> None:
    from splitbrain import seed
    from splitbrain.agents.sentinel import Sentinel
    from splitbrain.tui import CandidateLink, ClaimView

    view = SentinelTui(_llm(), width=120, height=32)  # type: ignore[arg-type]
    view.add_candidate(
        CandidateLink(
            candidate_id="sb-0001",
            a=ClaimView("sales", "maria", "SSO", "Acme", "Dec 1", "clm_1"),
            b=ClaimView("engineering", "tomas", "SSO", "*", "Q4 removed", "clm_2"),
            confidence=0.9,
            reason="dates",
        )
    )
    view.add_step("sb-0001", "candidate", "candidate sent", at="00:42:19")
    sentinel = Sentinel(
        agent=object(),  # type: ignore[arg-type]
        llm=object(),  # type: ignore[arg-type]
        store=object(),  # type: ignore[arg-type]
        state=seed.synthetic_state(),
        tui=view,
    )
    sentinel.rooms["r-conflict"] = "conflict-sb-0001-sso"
    sentinel._note_conflict_room("r-conflict")
    room_step = next(s for s in view.steps["sb-0001"] if s.text.startswith("room #"))
    assert room_step.text == "room #conflict-sb-0001-sso"
    assert room_step.at != "00:43:17"
    # A later sb:decided must not restamp the room step.
    view.add_step("sb-0001", "room", "room #LATE", at="00:43:17")
    assert [s.text for s in view.steps["sb-0001"]].count("room #conflict-sb-0001-sso") == 1


def test_tui_log_lines_are_time_and_event_only() -> None:
    from splitbrain.agents.base import LOG_DATE_FORMAT, TUI_LOG_FORMAT

    formatter = logging.Formatter(TUI_LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    record = logging.LogRecord(
        "splitbrain.agents.sentinel",
        logging.INFO,
        "sentinel.py",
        1,
        "Asked @%s for consent in #%s (%s)",
        ("tomas", "engineering", "sb-1847"),
        None,
    )
    line = formatter.format(record)
    assert "INFO" not in line
    assert "splitbrain.agents.sentinel" not in line
    assert line.endswith("Asked @tomas for consent in #engineering (sb-1847)")
