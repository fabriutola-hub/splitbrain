"""Model-free candidate pairing by subject, scope and polarity."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

from .models import Claim, ClaimStatus
from .store import pair_id

SUBJECT_SIMILARITY = 88


@dataclass(frozen=True, slots=True)
class MatchReport:
    matches: list[Claim]
    skip_reasons: tuple[str, ...]


def _same_subject(new: Claim, stored: Claim) -> bool:
    if new.subject_key == stored.subject_key:
        return True
    return fuzz.token_set_ratio(new.subject, stored.subject) >= SUBJECT_SIMILARITY


def _compatible_scope(new: Claim, stored: Claim) -> bool:
    return new.scope_key == stored.scope_key or new.scope_key == "*" or stored.scope_key == "*"


def match_report(
    new: Claim,
    stored: Sequence[Claim],
    *,
    pairs_seen: Iterable[str] = (),
) -> MatchReport:
    """Find active claims in a different room that could conflict with `new`."""
    seen = set(pairs_seen)
    matches: list[Claim] = []
    reasons: list[str] = []
    for other in stored:
        if other.status != ClaimStatus.ACTIVE:
            continue
        if other.room_id == new.room_id:
            reasons.append("same room")
            continue
        if pair_id(new, other) in seen:
            reasons.append("pair already seen")
            continue
        if other.author.casefold() == new.author.casefold():
            reasons.append("same author")
            continue
        if not _same_subject(new, other):
            reasons.append("different subject")
            continue
        if not _compatible_scope(new, other):
            reasons.append("different scope")
            continue
        matches.append(other)
    return MatchReport(matches=matches, skip_reasons=tuple(sorted(set(reasons))))


def find_matches(
    new: Claim,
    stored: Sequence[Claim],
    *,
    pairs_seen: Iterable[str] = (),
) -> list[Claim]:
    return match_report(new, stored, pairs_seen=pairs_seen).matches
