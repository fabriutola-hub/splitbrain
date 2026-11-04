"""Decision protocol state machine for a conflict room (SPEC section 4.6 step 5).

Only the two claim authors count. No model is used: people's words are recorded
verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

PROPOSAL_RE = re.compile(r"^\s*(?:decision|decisión)\s*:\s*(.+?)\s*$", re.IGNORECASE)
CONFIRM_RE = re.compile(r"^\s*(?:confirm|confirmo|agree|de acuerdo)\b", re.IGNORECASE)


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

    def _outcome(self, reply: str | None = None) -> DecisionOutcome:
        return DecisionOutcome(
            state=self.state,
            reply=reply,
            decision=self.decision,
            proposed_by=self.proposed_by,
            confirmed_by=self.confirmed_by,
            decided_at=self.decided_at,
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
            return self._outcome()

        if CONFIRM_RE.match(text):
            if self.state != DecisionState.PROPOSED:
                return self._outcome("There is no pending decision to confirm.")
            if author == self.proposed_by:
                other = self.authors[1] if author == self.authors[0] else self.authors[0]
                return self._outcome(f"Only @{other} can confirm this decision.")
            self.confirmed_by = author
            self.decided_at = datetime.now(UTC).isoformat(timespec="seconds")
            self.state = DecisionState.DECIDED
            return self._outcome()

        return self._outcome()
