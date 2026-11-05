"""Decision protocol state machine for a conflict room.

Only the two claim authors count. No model is used: people's words are recorded
verbatim. Confirmations are the short, natural phrases a person actually types
("Confirmed, I'll email them now."), not a strict command grammar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

PROPOSAL_RE = re.compile(r"^\s*(?:decision|decisión)\s*:\s*(.+?)\s*$", re.IGNORECASE)

# Longer phrases first: "confirmed" must win over "confirm", "okay" over "ok".
# A confirmation has to start the message; the tail lookahead accepts trailing
# punctuation or extra words but rejects a longer word ("confirmation", "since").
CONFIRM_WORDS: tuple[str, ...] = (
    "sounds good",
    "de acuerdo",
    "confirmed",
    "confirmo",
    "approved",
    "aprobado",
    "agreed",
    "agree",
    "confirm",
    "okay",
    "lgtm",
    "yes",
    "yep",
    "ok",
    "sí",
    "👍",
    "✅",
)
CONFIRM_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(word) for word in CONFIRM_WORDS) + r")(?=$|[^\w]|_)",
    re.IGNORECASE,
)
# A contrast after the confirmation word means the person has not agreed yet.
# "si" (Spanish for "if") is deliberately absent from CONFIRM_WORDS.
CONTRAST_RE = re.compile(r"\b(?:but|pero|not|no)\b", re.IGNORECASE)
LITERAL_CONFIRM_RE = re.compile(r"^\s*confirm[.!?]*\s*$", re.IGNORECASE)


class DecisionState(StrEnum):
    OPEN = "open"
    PROPOSED = "proposed"
    DECIDED = "decided"


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    state: DecisionState
    reply: str | None
    decision: str | None
    proposed_by: str | None
    confirmed_by: str | None
    decided_at: str | None
    announce: bool = False


class DecisionMachine:
    def __init__(self, author_a: str, author_b: str) -> None:
        if author_a == author_b:
            raise ValueError("A conflict needs two different authors")
        self.authors: tuple[str, str] = (author_a, author_b)
        self.state = DecisionState.OPEN
        self.decision: str | None = None
        self.proposed_by: str | None = None
        self.confirmed_by: str | None = None
        self.decided_at: str | None = None
        self._warned_intruders: set[str] = set()

    def _other(self, author: str) -> str:
        return self.authors[1] if author == self.authors[0] else self.authors[0]

    def _outcome(self, reply: str | None = None, *, announce: bool = False) -> DecisionOutcome:
        return DecisionOutcome(
            state=self.state,
            reply=reply,
            decision=self.decision,
            proposed_by=self.proposed_by,
            confirmed_by=self.confirmed_by,
            decided_at=self.decided_at,
            announce=announce,
        )

    def handle(self, author: str, text: str) -> DecisionOutcome:
        if author not in self.authors:
            if author in self._warned_intruders:
                return self._outcome()
            self._warned_intruders.add(author)
            return self._outcome(
                f"Only @{self.authors[0]} and @{self.authors[1]} can close this conflict."
            )

        if self.state == DecisionState.DECIDED:
            return self._outcome()

        proposal = PROPOSAL_RE.match(text)
        if proposal:
            # A new proposal replaces a pending one, even from the other author.
            self.decision = proposal.group(1)
            self.proposed_by = author
            self.confirmed_by = None
            self.state = DecisionState.PROPOSED
            return self._outcome(
                f'Proposal from @{author}: "{self.decision}". '
                f"@{self._other(author)}, reply confirm to close it, "
                "or write your own decision: ...",
                announce=True,
            )

        confirmation = CONFIRM_RE.match(text)
        if confirmation and not CONTRAST_RE.search(text[confirmation.end() :]):
            if self.state != DecisionState.PROPOSED:
                # Natural words are conversation, not a command: only the literal
                # "confirm" deserves a correction when nothing is open.
                if LITERAL_CONFIRM_RE.match(text):
                    return self._outcome("There is no pending decision to confirm.")
                return self._outcome()
            if author == self.proposed_by:
                return self._outcome(f"Only @{self._other(author)} can confirm this decision.")
            self.confirmed_by = author
            self.decided_at = datetime.now(UTC).isoformat(timespec="seconds")
            self.state = DecisionState.DECIDED
            return self._outcome()

        return self._outcome()
