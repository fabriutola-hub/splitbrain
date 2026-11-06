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

from pydantic import BaseModel, Field

PROPOSAL_RE = re.compile(r"^\s*(?:decision|decisión)\s*:\s*(.+?)\s*$", re.IGNORECASE)
TERMINAL_PUNCTUATION = (".", "!", "?")


def quoted_sentence(text: str) -> str:
    """A quoted literal as a sentence, never with a doubled full stop.

    Mattermost renders `@maria` as `@María Gómez`; a proposal whose text already
    ends in ".", "!" or "?" must not get another "." after the closing quote.
    """
    ending = "" if text.rstrip().endswith(TERMINAL_PUNCTUATION) else "."
    return f'"{text}"{ending}'


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
CONDITIONAL_RE = re.compile(
    r"[?¿]|\b(?:if|unless|but|pending|once|after|tomorrow|later|maybe|until|"
    r"not|no|perhaps|unsure|si|pero|cuando|mañana|luego|revisamos|depende|"
    r"a menos que|quizás|quiza|todavía)\b",
    re.IGNORECASE,
)
VERSION_RE = re.compile(r"\bv(\d+)\b", re.IGNORECASE)
CONFLICT_RE = re.compile(r"\bsb-[a-z0-9]+\b", re.IGNORECASE)
LITERAL_CONFIRM_RE = re.compile(r"^\s*confirm[.!?]*\s*$", re.IGNORECASE)


class DecisionState(StrEnum):
    OPEN = "open"
    PROPOSED = "proposed"
    DECIDED = "decided"


class Proposal(BaseModel):
    version: int = Field(ge=1)
    author: str
    text: str
    message_id: str = ""
    timestamp: int = 0
    thread_ids: list[str] = Field(default_factory=list)


class Confirmation(BaseModel):
    version: int = Field(ge=1)
    author: str
    message_id: str = ""
    timestamp: int = 0
    confirmed_at: str


class DecisionSnapshot(BaseModel):
    conflict_id: str
    authors: tuple[str, str]
    state: DecisionState = DecisionState.OPEN
    version: int = Field(default=0, ge=0)
    proposals: list[Proposal] = Field(default_factory=list)
    confirmations: list[Confirmation] = Field(default_factory=list)
    processed_messages: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    state: DecisionState
    reply: str | None
    decision: str | None
    proposed_by: str | None
    confirmed_by: str | None
    decided_at: str | None
    announce: bool = False
    version: int = 0


class DecisionMachine:
    def __init__(self, author_a: str, author_b: str, *, conflict_id: str = "") -> None:
        if author_a == author_b:
            raise ValueError("A conflict needs two different authors")
        self.authors: tuple[str, str] = (author_a, author_b)
        self.conflict_id = conflict_id
        self.version = 0
        self.proposals: list[Proposal] = []
        self.confirmations: list[Confirmation] = []
        self.processed_messages: set[str] = set()
        self._clock = 0
        self.state = DecisionState.OPEN
        self.decision: str | None = None
        self.proposed_by: str | None = None
        self.confirmed_by: str | None = None
        self.decided_at: str | None = None
        self._warned_intruders: set[str] = set()

    def snapshot(self) -> DecisionSnapshot:
        return DecisionSnapshot(
            conflict_id=self.conflict_id,
            authors=self.authors,
            state=self.state,
            version=self.version,
            proposals=self.proposals,
            confirmations=self.confirmations,
            processed_messages=sorted(self.processed_messages),
        ).model_copy(deep=True)

    @classmethod
    def restore(cls, snapshot: DecisionSnapshot) -> DecisionMachine:
        machine = cls(*snapshot.authors, conflict_id=snapshot.conflict_id)
        machine.state = snapshot.state
        machine.version = snapshot.version
        machine.proposals = [item.model_copy(deep=True) for item in snapshot.proposals]
        machine.confirmations = [item.model_copy(deep=True) for item in snapshot.confirmations]
        machine.processed_messages = set(snapshot.processed_messages)
        if snapshot.version:
            if [item.version for item in snapshot.proposals] != list(
                range(1, snapshot.version + 1)
            ):
                raise ValueError("Decision record has a missing proposal version")
            proposal = machine.proposals[-1]
            if proposal.author not in machine.authors:
                raise ValueError("Decision record has a proposal from a non-owner")
            machine.decision = proposal.text
            machine.proposed_by = proposal.author
            machine._clock = proposal.timestamp
        if snapshot.state == DecisionState.DECIDED:
            confirmation = next(
                (
                    item
                    for item in reversed(machine.confirmations)
                    if item.version == machine.version
                ),
                None,
            )
            if (
                not machine.proposals
                or confirmation is None
                or confirmation.author not in machine.authors
                or confirmation.author == machine.proposed_by
            ):
                raise ValueError("DECIDED record requires the other owner's confirmation")
            machine.confirmed_by = confirmation.author
            machine.decided_at = confirmation.confirmed_at
        elif snapshot.state != (DecisionState.PROPOSED if snapshot.version else DecisionState.OPEN):
            raise ValueError("Decision record state disagrees with its proposal version")
        return machine

    def bind_announcement(self, message_id: str) -> None:
        if message_id and self.proposals and message_id not in self.proposals[-1].thread_ids:
            self.proposals[-1].thread_ids.append(message_id)

    def proposal_reply(self) -> str:
        return (
            f"Proposal v{self.version} from @{self.proposed_by}: "
            f"{quoted_sentence(self.decision or '')} "
            f"@{self._other(self.proposed_by or '')}, reply confirm to close it, "
            "or write your own decision: ..."
        )

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
            version=self.version,
        )

    def handle(
        self,
        author: str,
        text: str,
        *,
        message_id: str = "",
        timestamp: int | None = None,
        thread_id: str | None = None,
        sender_kind: str | None = None,
    ) -> DecisionOutcome:
        if (sender_kind or "").casefold() in {"agent", "platform"} or author.casefold().startswith(
            "splitbrain-"
        ):
            return self._outcome()
        if self.state == DecisionState.DECIDED or (
            message_id and message_id in self.processed_messages
        ):
            return self._outcome()
        if author not in self.authors:
            if author in self._warned_intruders:
                return self._outcome()
            self._warned_intruders.add(author)
            return self._outcome(
                f"Only @{self.authors[0]} and @{self.authors[1]} can close this conflict."
            )

        proposal = PROPOSAL_RE.match(text)
        if proposal:
            # A new proposal replaces a pending one, even from the other author.
            self.decision = proposal.group(1)
            self.proposed_by = author
            self.confirmed_by = None
            self.decided_at = None
            self.version += 1
            # Without transport metadata, direct callers use local call order.
            # A transport timestamp of zero is unknown, never evidence of order.
            self._clock = max(self._clock + 1, int(datetime.now(UTC).timestamp() * 1000))
            self.proposals.append(
                Proposal(
                    version=self.version,
                    author=author,
                    text=self.decision,
                    message_id=message_id,
                    timestamp=self._clock if timestamp is None else timestamp,
                    thread_ids=[message_id] if message_id else [],
                )
            )
            if message_id:
                self.processed_messages.add(message_id)
            self.state = DecisionState.PROPOSED
            return self._outcome(
                self.proposal_reply(),
                announce=True,
            )

        confirmation = CONFIRM_RE.match(text.lstrip(" \t\r\n¿"))
        if confirmation:
            if self.state != DecisionState.PROPOSED:
                # Natural words are conversation, not a command: only the literal
                # "confirm" deserves a correction when nothing is open.
                if LITERAL_CONFIRM_RE.match(text):
                    return self._outcome("There is no pending decision to confirm.")
                return self._outcome()
            if author == self.proposed_by:
                return self._outcome(f"Only @{self._other(author)} can confirm this decision.")
            if CONDITIONAL_RE.search(text):
                return self._outcome(
                    f"That reply is conditional or uncertain, so v{self.version} is still open. "
                    "Reply confirm when it is final."
                )
            versions = [int(value) for value in VERSION_RE.findall(text)]
            conflicts = [value.casefold() for value in CONFLICT_RE.findall(text)]
            if any(version != self.version for version in versions) or any(
                value != self.conflict_id.casefold() for value in conflicts
            ):
                return self._outcome(
                    f"That reply names another proposal. v{self.version} is still open. "
                    f"Reply confirm {self.conflict_id} v{self.version} when it is final."
                )
            current = self.proposals[-1]
            old_threads = {value for item in self.proposals[:-1] for value in item.thread_ids}
            if thread_id and thread_id in old_threads and thread_id not in current.thread_ids:
                return self._outcome(
                    f"That reply belongs to an older proposal; v{self.version} is still open. "
                    "Confirm in the current proposal's thread."
                )
            explicit = bool(versions and conflicts)
            in_thread = bool(thread_id and thread_id in current.thread_ids)
            after = timestamp is None or (
                timestamp > 0 and current.timestamp > 0 and timestamp > current.timestamp
            )
            if not (explicit or in_thread or after) or (conflicts and not versions):
                return self._outcome(
                    f"I cannot tie that reply to v{self.version}; it is still open. "
                    f"Reply confirm {self.conflict_id} v{self.version} when it is final."
                )
            self.confirmed_by = author
            self.decided_at = datetime.now(UTC).isoformat(timespec="seconds")
            self.confirmations.append(
                Confirmation(
                    version=self.version,
                    author=author,
                    message_id=message_id,
                    timestamp=timestamp or int(datetime.now(UTC).timestamp() * 1000),
                    confirmed_at=self.decided_at,
                )
            )
            if message_id:
                self.processed_messages.add(message_id)
            self.state = DecisionState.DECIDED
            return self._outcome()

        return self._outcome()
