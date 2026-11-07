"""Versioned decision snapshots and the Sentinel's per-thread correction journal.

Each writer owns its document: a standby can save a recovery snapshot without
editing another agent's document. The human record stays readable without JSON.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..switch.client import SwitchAgent, SwitchOpError, lost_room_context
from .decision import DecisionMachine, DecisionSnapshot, DecisionState
from .protocol import CandidatePacket, DecidedPacket, OriginRef

STATE_PREFIX = "\n\nSplitbrain state: "
PROGRESS_PREFIX = "\n\nSplitbrain corrections: "
CONTEXT_LIMIT = 200

logger = logging.getLogger(__name__)


class CorrectionProgress(BaseModel):
    room_id: str
    room_name: str
    thread_id: str
    status: Literal["pending", "posted"] = "pending"
    message_id: str = ""

    @model_validator(mode="after")
    def require_receipt(self) -> CorrectionProgress:
        if self.status == "posted" and not self.message_id:
            raise ValueError("A posted correction requires its message id")
        return self


def pending_corrections(origins: list[OriginRef]) -> list[CorrectionProgress]:
    unique = {(origin.room_id, origin.thread_id): origin for origin in origins}
    return [
        CorrectionProgress(
            room_id=origin.room_id, room_name=origin.room_name, thread_id=origin.thread_id
        )
        for origin in unique.values()
    ]


class DecisionRecord(BaseModel):
    schema_version: Literal[1] = 1
    candidate: CandidatePacket
    machine: DecisionSnapshot
    origins: list[OriginRef]
    ops_thread_id: str
    writer: str
    revision: int = Field(default=0, ge=0)
    decision_announced: bool = False
    followup_logged: bool = False
    decision_sent: bool = False
    corrected: bool = False
    corrections: list[CorrectionProgress] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_matching_conflict(self) -> DecisionRecord:
        if self.machine.conflict_id != self.candidate.id or self.machine.authors != tuple(
            claim.author for claim in self.candidate.claims
        ):
            raise ValueError("Decision snapshot disagrees with its conflict or owners")
        DecisionMachine.restore(self.machine)
        return self


class CorrectionJournal(BaseModel):
    schema_version: Literal[1] = 1
    decided: DecidedPacket
    threads: list[CorrectionProgress]
    notified: bool = False

    @model_validator(mode="after")
    def require_all_origins(self) -> CorrectionJournal:
        expected = {(origin.room_id, origin.thread_id) for origin in self.decided.origins}
        actual = [(item.room_id, item.thread_id) for item in self.threads]
        if set(actual) != expected or len(actual) != len(expected):
            raise ValueError("Correction journal must contain each original thread exactly once")
        if self.notified and not self.complete:
            raise ValueError("An incomplete correction journal cannot be acknowledged")
        return self

    @property
    def complete(self) -> bool:
        return bool(self.threads) and all(
            item.status == "posted" and item.message_id for item in self.threads
        )

    def render(self) -> str:
        lines = [
            f"{self.decided.candidate_id.upper()} correction progress",
            "Status: corrected" if self.complete else "Status: pending",
            *[
                f"#{item.room_name} / {item.thread_id}: {item.status}"
                + (f" ({item.message_id})" if item.message_id else "")
                for item in self.threads
            ],
        ]
        return "\n".join(lines) + PROGRESS_PREFIX + self.model_dump_json()


@dataclass
class StoredDecision:
    document_id: str
    content: str
    state: DecisionRecord | None


def record_body(content: str) -> str:
    return content.rpartition(STATE_PREFIX)[0] if STATE_PREFIX in content else content


def render_record(content: str, state: DecisionRecord) -> str:
    return record_body(content).rstrip() + STATE_PREFIX + state.model_dump_json()


async def _load_documents(agent: SwitchAgent, room_id: str, ids: list[str]) -> Any:
    """Read under the caller's room claim; reconnect once for the known context loss."""
    try:
        return await agent.op("load_internal_documents", ids=ids)
    except SwitchOpError as exc:
        if not lost_room_context(exc):
            raise
        logger.warning(
            "Switch lost room context for %s while loading documents; "
            "reconnecting and retrying once",
            room_id,
        )
        await agent.op("connect_to_room", room_id=room_id)
        return await agent.op("load_internal_documents", ids=ids)


def _decision_document_ids(joined: dict[str, Any], candidate_id: str) -> list[str]:
    base = f"{candidate_id.upper()} decision record"
    return [
        str(doc["id"])
        for doc in joined.get("documents") or []
        if doc.get("id")
        and (doc.get("name") == base or str(doc.get("name", "")).startswith(base + " ("))
    ]


async def read_decision_records(
    agent: SwitchAgent, room_id: str, candidate_id: str, joined: dict[str, Any]
) -> tuple[list[StoredDecision], list[dict[str, Any]]]:
    """Read the records while the caller already holds the room claim in `joined`."""
    ids = _decision_document_ids(joined, candidate_id)
    loaded = await _load_documents(agent, room_id, ids) if ids else []
    entries = loaded if isinstance(loaded, list) else loaded.get("documents", [])
    if len(entries) != len(ids):
        raise ValueError("A listed decision document could not be loaded; refusing to reopen it")
    records = []
    for index, entry in enumerate(entries):
        content = str(entry.get("content", ""))
        state = (
            DecisionRecord.model_validate_json(content.rpartition(STATE_PREFIX)[2])
            if STATE_PREFIX in content
            else None
        )
        if state is not None and state.candidate.id != candidate_id:
            raise ValueError("Decision document belongs to another conflict")
        records.append(StoredDecision(str(entry.get("id") or ids[index]), content, state))
    return records, joined.get("linked_rooms") or []


async def load_decision_records(
    agent: SwitchAgent, room_id: str, candidate_id: str
) -> tuple[list[StoredDecision], list[dict[str, Any]]]:
    async with agent.act_in(room_id):
        joined = await agent.op("connect_to_room", room_id=room_id)
        return await read_decision_records(agent, room_id, candidate_id, joined)


def latest_record(records: list[StoredDecision]) -> StoredDecision | None:
    # A persisted final decision always beats an OPEN snapshot, even if an old
    # holder managed to save one more OPEN revision during a lease handoff.
    return max(
        records,
        key=lambda item: (
            item.state.machine.state == DecisionState.DECIDED
            if item.state
            else "Status: DECIDED" in item.content,
            item.state.machine.version if item.state else 0,
            item.state.revision if item.state else 0,
        ),
        default=None,
    )


async def read_correction_journal(
    agent: SwitchAgent, room_id: str, candidate_id: str, joined: dict[str, Any]
) -> tuple[str, CorrectionJournal | None]:
    """Read the journal while the caller already holds the room claim in `joined`."""
    ids = [
        str(doc["id"])
        for doc in joined.get("documents") or []
        if doc.get("id") and doc.get("name") == f"{candidate_id.upper()} correction progress"
    ]
    if not ids:
        return "", None
    if len(ids) != 1:
        raise ValueError("Correction journal is ambiguous")
    document_id = ids[0]
    loaded = await _load_documents(agent, room_id, [document_id])
    entries = loaded if isinstance(loaded, list) else loaded.get("documents", [])
    if len(entries) != 1:
        raise ValueError("Correction journal is missing or ambiguous")
    content = str(entries[0].get("content", ""))
    if PROGRESS_PREFIX not in content:
        raise ValueError("Correction journal has no durable progress")
    journal = CorrectionJournal.model_validate_json(content.rpartition(PROGRESS_PREFIX)[2])
    if journal.decided.candidate_id != candidate_id:
        raise ValueError("Correction journal belongs to another conflict")
    return document_id, journal


async def load_correction_journal(
    agent: SwitchAgent, room_id: str, candidate_id: str
) -> tuple[str, CorrectionJournal | None]:
    async with agent.act_in(room_id):
        joined = await agent.op("connect_to_room", room_id=room_id)
        return await read_correction_journal(agent, room_id, candidate_id, joined)


def message_id(result: dict[str, Any]) -> str:
    return str(result.get("event_id") or result.get("message_id") or result.get("id") or "")


def posted_message(
    context: dict[str, Any],
    body: str,
    senders: set[str],
    *,
    thread_id: str | None = None,
) -> str:
    for thread in context.get("threads", []):
        root = thread.get("root") or {}
        if thread_id is not None and message_id(root) != thread_id:
            continue
        for entry in [root, *(thread.get("replies") or [])]:
            if entry.get("body") == body and entry.get("sender_name") in senders:
                return message_id(entry)
    return ""
