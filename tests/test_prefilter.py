"""Signal-based prefilter, at least 20 examples."""

from __future__ import annotations

import pytest

from splitbrain.core.models import Message
from splitbrain.core.prefilter import keep, prefilter


def msg(
    text: str, *, author: str = "maria", room: str = "sales", kind: str | None = None
) -> Message:
    return Message(
        message_id="m1",
        room_id=room,
        room_name=room,
        author=author,
        sender_kind=kind,
        text=text,
    )


@pytest.mark.parametrize(
    "text",
    [
        "Confirmed with Acme that SSO will be live for them on December 1.",
        "Morning all, the Q4 launch is locked for November 15.",
        "We are pulling SSO out of Q1 2027, migration comes first.",
        "The new uptime SLA is 99.9% from January.",
        "Refunds over $500 need a manager approval before processing.",
        "We are raising the API limit to 1000 requests per minute on Monday.",
        "The 10% price increase goes live on 2026-12-01 for everyone.",
        "Standard invoice terms are net 30 starting next Thursday.",
        "We will not ship the audit log export this quarter.",
        "SSO is no longer in the Q4 release, we moved it to Q1.",
        "Confirmé con Acme que SSO sale el 1 de diciembre.",
        "La política de reembolsos cambia a 500 USD desde marzo.",
        "Posponemos el lanzamiento hasta el viernes, aviso a todos.",
        "Lanzamos la beta el 15 de diciembre para todos los clientes.",
        "Confirmé que los reembolsos requieren aprobación del gerente desde hoy.",
        "Are we still shipping the December SSO beta to Acme next week?",
        "If we pull SSO from Q4, Acme will probably ask for a credit.",
        "Reminder: refunds above $250 still require manager approval until Friday.",
        "There is a vacation blackout from December 20 to December 31.",
        "We will deliver 50 seats for the enterprise plan by Friday.",
    ],
)
def test_commitment_signals_are_kept(text: str) -> None:
    decision = prefilter(msg(text))
    assert decision.keep, f"should keep {text!r}: {decision.reason}"


@pytest.mark.parametrize(
    ("text", "author", "room", "kind", "reason"),
    [
        ("Happy birthday everyone, great work this week!", "maria", "sales", None, "signal"),
        ("Thanks for the update team, much appreciated!", "lucia", "support", None, "signal"),
        ("No decision yet, just thinking out loud here.", "tomas", "engineering", None, "signal"),
        ("Let us grab coffee after the standup tomorrow.", "priya", "product", None, "signal"),
        ("SSO delayed", "maria", "sales", None, "fewer than"),
        ("Confirmed with Acme SSO for December.", "splitbrain-sentinel", "sales", None, "agents"),
        ("Confirmed with Acme SSO for December.", "maria", "sales", "platform", "platform"),
        ("Confirmed with Acme SSO for December.", "maria", "splitbrain-ops", None, "internal"),
        (
            "Confirmed with Acme SSO for December.",
            "maria",
            "conflict-sb-0001-sso",
            None,
            "internal",
        ),
        ("Confirmed with Acme SSO for December.", "splitbrain-arbiter-b", "sales", None, "agents"),
    ],
)
def test_drops(text: str, author: str, room: str, kind: str | None, reason: str) -> None:
    decision = prefilter(msg(text, author=author, room=room, kind=kind))
    assert not decision.keep
    assert reason in decision.reason


def test_keep_is_the_boolean_shortcut() -> None:
    assert keep(msg("We will ship SSO on December 1 to Acme."))
    assert not keep(msg("Happy birthday everyone, great work this week!"))


def test_five_words_is_the_boundary() -> None:
    assert not prefilter(msg("SSO will ship December")).keep
    assert prefilter(msg("SSO will ship on December 1")).keep
