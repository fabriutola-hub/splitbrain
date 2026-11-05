"""Cheap, model-free prefilter for incoming chat messages."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Message

OWN_AGENT_PREFIX = "splitbrain-"
SILENT_ROOMS = frozenset({"splitbrain-ops"})
MIN_WORDS = 5

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|"
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|"
    "ene|abr|ago|dic"
)
_WEEKDAYS = (
    "monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    "mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun|"
    "lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo"
)
_VERBS = (
    "promise|confirm|commit|ship|launch|release|deliver|cut|drop|pull|delay|move|postpone|"
    "cancel|change|policy|refund|deadline|guarantee|approve|decide|schedule|pledge|"
    "require|extend|raise|lower|increase|reduce|freeze|will|won't|"
    "promet|sale|salga|lanz|recort|sac|mov|pospon|cancel|cambi|política|politica|"
    "reembolso|plazo|aprob|decid|fij|sube|baja|aplaz|activ|desactiv"
)

_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b", re.IGNORECASE
)
_MONTH_RE = re.compile(rf"\b(?:{_MONTHS})\b\.?", re.IGNORECASE)
_WEEKDAY_RE = re.compile(rf"\b(?:{_WEEKDAYS})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\bq[1-4]\b|\bquarter\s*[1-4]\b", re.IGNORECASE)
_NUMBER_UNIT_RE = re.compile(
    r"(?:\$\s?\d|\d[\d,.]*\s*(?:%|percent|usd|eur|gbp|€|£|\$|hours?|hrs?|days?|weeks?|"
    r"months?|years?|minutes?|seconds?|ms|gb|mb|requests?|rps|users?|seats?|licen[cs]es?|"
    r"tickets?|calls?)\b)",
    re.IGNORECASE,
)
_VERB_RE = re.compile(rf"\b(?:{_VERBS})\w*\b", re.IGNORECASE)
_NO_LONGER_RE = re.compile(r"\bno longer\b|\bya no\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class PrefilterDecision:
    keep: bool
    reason: str


def _has_commitment_signal(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in (
            _DATE_RE,
            _MONTH_RE,
            _WEEKDAY_RE,
            _QUARTER_RE,
            _NUMBER_UNIT_RE,
            _VERB_RE,
            _NO_LONGER_RE,
        )
    )


def prefilter(message: Message) -> PrefilterDecision:
    """Decide whether a message is worth sending to the model."""
    author = message.author.strip().casefold()
    if author.startswith(OWN_AGENT_PREFIX):
        return PrefilterDecision(False, "message from one of our own agents")
    if (message.sender_kind or "").casefold() == "platform":
        return PrefilterDecision(False, "platform message")
    room = message.room_name.strip().casefold()
    if room in SILENT_ROOMS or room.startswith("conflict-"):
        return PrefilterDecision(False, "message in an internal Splitbrain room")
    words = message.text.split()
    if len(words) < MIN_WORDS:
        return PrefilterDecision(False, f"fewer than {MIN_WORDS} words")
    if not _has_commitment_signal(message.text):
        return PrefilterDecision(False, "no commitment signal (pure chatter)")
    return PrefilterDecision(True, "commitment signal")


def keep(message: Message) -> bool:
    return prefilter(message).keep
