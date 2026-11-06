"""Cheap, model-free prefilter for incoming chat messages."""

from __future__ import annotations

import re
import unicodedata
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
    "promis|confirm|commit|ship|launch|releas|deliver|cut|drop|pull|delay|mov|postpon|"
    "cancel|chang|policy|refund|deadline|guarant|approv|decid|schedul|pledg|"
    "requir|extend|rais|lower|increas|reduc|freez|will|won't|"
    "promet|sale|salga|lanz|recort|sac|mov|pospon|cancel|cambi|política|politica|"
    "reembolso|plazo|aprob|decid|fij|sube|baja|aplaz|activ|desactiv"
)
_NUMBER = r"\d+(?:[.,]\d+)*"
_NUMBER_WORDS = (
    "zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    "thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    "thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
    "cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
    "trece|catorce|quince|dieciseis|diecisiete|dieciocho|diecinueve|veinte|"
    "treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|mil"
)
_PERIODS = "day|week|month|quarter|year"
_PERIODS_ES = "dia|semana|mes|trimestre|ano"
# Function words after a number are not units ("one of us", "three of them").
_NON_UNITS = frozenset(
    "of de del the a an to or and more less is was are were es son y o que for para".split()
)

_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b", re.IGNORECASE
)
_MONTH_RE = re.compile(rf"\b(?:{_MONTHS})\b\.?", re.IGNORECASE)
_WEEKDAY_RE = re.compile(rf"\b(?:{_WEEKDAYS})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\bq[1-4]\b|\bquarter\s*[1-4]\b", re.IGNORECASE)
_NUMBER_UNIT_RE = re.compile(
    rf"(?<!\w)(?:{_NUMBER}|(?:{_NUMBER_WORDS})\b)"
    r"\s*[-–]?\s*(?P<unit>[^\W\d_]+|[^\w\s])",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(r"(?P<symbol>[^\w\s])\s*\d")
_RANGE_RE = re.compile(rf"(?<!\w){_NUMBER}\s*(?:[-–—]|to|through|hasta|a)\s*{_NUMBER}\b")
_VERB_RE = re.compile(rf"\b(?:{_VERBS})\w*\b", re.IGNORECASE)
_CONTRACT_VERB_RE = re.compile(
    r"\b(?:(?:sign|grant|restrict|prohibit|renew)(?:s|ed|ing)?|cap(?:s|ped|ping)?|"
    r"(?:authoriz|authoris|revok)(?:e|es|ed|ing)|ratif(?:y|ies|ied|ying)|"
    r"(?:compromet|compromis|garantiz|exig|oblig|autoriz|prohib|firm|revoc|otorg|"
    r"restring|permit)[aeiou]\w*)\b",
    re.IGNORECASE,
)
_OBLIGATION_RE = re.compile(
    r"\b(?:must|shall|(?:has|have|had|need|needs|needed)\s+to|"
    r"(?:i|we|you|they|he|she)['’]ll|(?:am|is|are)\s+going\s+to|"
    r"(?:i['’]m|(?:we|you|they)['’]re|(?:he|she|it)['’]s)\s+going\s+to|"
    r"debe(?:n|mos|ra\w*)?|tiene[n]?\s+que|hay\s+que)\b",
    re.IGNORECASE,
)
_NO_LONGER_RE = re.compile(
    r"\b(?:no longer|not anymore|ya no)\b|\bnot\b[^.!?\n]*\banymore\b", re.IGNORECASE
)
_DEADLINE_RE = re.compile(
    rf"\b(?:by|before|until|from|in|during|for|starting)\s+"
    rf"(?:this|next|following)\s+(?:{_PERIODS})\b|"
    rf"\b(?:start|end|beginning)\s+of\s+(?:(?:the|this|next)\s+)?(?:{_PERIODS})\b|"
    r"\b(?:by|before|until)\s+(?:today|tomorrow)\b|"
    r"\b(?:until further notice|going forward)\b|"
    rf"\b(?:para|hasta|desde|durante|el|la)\s+"
    rf"(?:este|esta|proximo|proxima|siguiente)\s+(?:{_PERIODS_ES})\b|"
    rf"\b(?:fin|final|principio|inicio)\s+de\s+(?:(?:el|la|este|esta)\s+)?"
    rf"(?:{_PERIODS_ES})\b|"
    r"\b(?:a partir de|antes de|hasta|para)\s+(?:hoy|manana)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PrefilterDecision:
    keep: bool
    reason: str


def _has_quantity(text: str) -> bool:
    for match in _NUMBER_UNIT_RE.finditer(text):
        unit = match["unit"]
        if unit.isalpha():
            if unit not in _NON_UNITS:
                return True
            continue
        # Symbols have no word boundary after them; punctuation is not a unit.
        if unicodedata.category(unit).startswith("S") or unit in {"%", "‰", "‱"}:
            return True
    return any(
        unicodedata.category(match["symbol"]) == "Sc" for match in _CURRENCY_RE.finditer(text)
    )


def _has_commitment_signal(text: str) -> bool:
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )
    return _has_quantity(text) or any(
        pattern.search(text)
        for pattern in (
            _DATE_RE,
            _MONTH_RE,
            _WEEKDAY_RE,
            _QUARTER_RE,
            _RANGE_RE,
            _VERB_RE,
            _CONTRACT_VERB_RE,
            _OBLIGATION_RE,
            _NO_LONGER_RE,
            _DEADLINE_RE,
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
