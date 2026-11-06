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


@pytest.mark.parametrize(
    "text",
    [
        "The hoist tolerance is 17 kN under load.",
        "The container capacity is 42l across the catalogue.",
        "The alloy specification allows 0.35% impurities overall.",
        "The fixture angle is 12° throughout production.",
        "The service deposit is ¥800 for each booking.",
        "The account balance floor is ₦900 for every member.",
        "The coating tolerance is 0,8‰ throughout production.",
        "The initial batch size is 11–14 across locations.",
        "The initial batch size is 11 — 14.",
        "The pack contains seven adapters in total.",
        "El paquete incluye nueve conectores por caja.",
        "El almacén admite 24 bidones por estante.",
        "La disponibilidad pactada es 97% para usuarios externos.",
    ],
)
def test_open_ended_quantities_are_kept(text: str) -> None:
    assert prefilter(msg(text)).keep


@pytest.mark.parametrize(
    "text",
    [
        "Legal signed the service agreement with Briar.",
        "Procurement capped the aggregate supplier liability yesterday.",
        "We are promising encrypted archives for every tenant.",
        "We are releasing the archive connector globally.",
        "Operations must retain encrypted backups for every tenant.",
        "The supplier has to retain encrypted backups indefinitely.",
        "We'll retain encrypted backups for every tenant.",
        "We’re going to retain encrypted backups indefinitely.",
        "El operador garantizará continuidad durante toda la migración.",
        "El acceso exige autenticación reforzada para externos.",
        "Nos comprometimos a mantener las copias disponibles.",
        "La entidad firmó el acuerdo de custodia.",
        "El equipo deberá conservar las copias cifradas.",
        "We are not accepting new tenants anymore.",
        "The old connector is not supported anymore.",
        "El servicio ya no admite solicitudes externas.",
    ],
)
def test_commitment_inflections_and_obligations_are_kept(text: str) -> None:
    assert prefilter(msg(text)).keep


@pytest.mark.parametrize(
    "text",
    [
        "General availability is set for the end of quarter.",
        "The service window is available from next month.",
        "The replacement takes effect by tomorrow across locations.",
        "The restriction remains until further notice for everyone.",
        "El acceso queda disponible antes de fin de trimestre.",
        "La renovación entra en vigor el próximo año.",
        "La ventana de mantenimiento termina para mañana.",
    ],
)
def test_relative_deadlines_are_kept(text: str) -> None:
    assert prefilter(msg(text)).keep


@pytest.mark.parametrize(
    "text",
    [
        "Hello everyone, lovely to see you here!",
        "Hola a todos, qué gusto verlos por aquí.",
        "Thanks everyone for helping out, much appreciated.",
        "Muchas gracias por la ayuda, excelente trabajo equipo.",
        "Who wants to join us for lunch?",
        "Anyone up for pizza after the meeting?",
        "¿Alguien quiere almorzar conmigo después de la reunión?",
        "Let us grab coffee after the standup tomorrow.",
        "Can anyone help me out here?",
        "Does anybody know what happened here?",
        "You are one of a kind indeed.",
        "It was three of us having lunch.",
        "The wireless signal looks much better over here.",
        "The firmware looks interesting from what I heard.",
        "The picture is numbered but looks nice.",
        "Well, that is 123, thanks everyone!",
        "Well, that is 123. Thanks everyone!",
        "No decision yet, just thinking out loud here.",
        "Signed the agreement",
        "El límite es 70%",
        "Confirmed, thanks!",
        "yes",
    ],
)
def test_chatter_and_short_messages_still_drop(text: str) -> None:
    assert not prefilter(msg(text)).keep
