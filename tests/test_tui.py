"""The rich Live view renders both columns and highlights the candidate link."""

from __future__ import annotations

from rich.console import Console

from splitbrain.tui import (
    HEIGHT,
    WIDTH,
    CandidateLink,
    ClaimView,
    IncomingMessage,
    SentinelTui,
)


def _render(view: SentinelTui) -> str:
    console = Console(width=WIDTH, height=HEIGHT, record=True)
    console.print(view.render())
    return console.export_text()


def test_render_shows_both_columns_and_a_120x32_console() -> None:
    view = SentinelTui()
    view.add_message("sales", "maria", "SSO will be live on December 1", True, "signal")
    view.add_claim(ClaimView("sales", "maria", "SSO", "Acme", "live on 2026-12-01", "clm_1"))
    output = _render(view)
    assert "INCOMING MESSAGES" in output
    assert "CLAIMS + CANDIDATE LINK" in output
    assert "SPLITBRAIN SENTINEL" in output
    assert "SSO will be live" in output
    assert view._console.width == WIDTH
    assert view._console.height == HEIGHT


def test_filtered_messages_are_dimmed() -> None:
    panel = SentinelTui._left(
        [IncomingMessage("support", "lucia", "hello there", False, "pure chatter")]
    )
    body = panel.renderable
    assert any(span.style == "dim" for span in body.spans)


def test_candidate_link_highlights_both_claims() -> None:
    view = SentinelTui()
    view.add_candidate(
        CandidateLink(
            candidate_id="sb-0001",
            a=ClaimView("sales", "maria", "SSO", "Acme", "live on 2026-12-01", "clm_1"),
            b=ClaimView("engineering", "tomas", "SSO", "*", "removed from Q4", "clm_2"),
            confidence=0.94,
            reason="Two different delivery dates.",
        )
    )
    output = _render(view)
    assert "CANDIDATE sb-0001" in output
    assert "CONTRADICTION" in output
    assert "live on 2026-12-01" in output
    assert "removed from Q4" in output
    assert view.candidates == 1


def test_log_handler_feeds_the_footer() -> None:
    view = SentinelTui()
    view.add_log("worker started")
    assert "worker started" in _render(view)
