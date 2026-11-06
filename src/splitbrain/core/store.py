"""SQLite persistence for the Sentinel.

Plain sqlite3 from the standard library. Sync statements run in a worker thread so
the agent's event loop never blocks on disk.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .models import Candidate, Claim, ClaimStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS claims_status ON claims(status);
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    published_at TEXT
);
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pairs_seen (
    pair_id TEXT PRIMARY KEY,
    seen_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    result TEXT,
    candidate_id TEXT,
    retryable INTEGER NOT NULL DEFAULT 1,
    new_claim_id TEXT,
    other_claim_id TEXT,
    finalized_at TEXT,
    updated_at TEXT
);
"""


class PairStatus(StrEnum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PairState:
    pair_id: str
    status: PairStatus
    attempts: int
    error: str | None
    result: dict[str, Any] | None
    candidate_id: str | None
    retryable: bool
    new_claim_id: str | None
    other_claim_id: str | None
    finalized_at: str | None
    seen_at: str


def pair_id(claim_a: Claim, claim_b: Claim) -> str:
    return "|".join(sorted((claim_a.id, claim_b.id)))


class ClaimStore:
    def __init__(self, path: Path | str = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._connection.executescript(_SCHEMA)
            self._migrate()
            self._connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _columns(self, table: str) -> set[str]:
        rows = self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def _migrate(self) -> None:
        candidate_columns = self._columns("candidates")
        if "published_at" not in candidate_columns:
            self._connection.execute("ALTER TABLE candidates ADD COLUMN published_at TEXT")
            # Older rows were published by the previous implementation; do not resend them.
            self._connection.execute("UPDATE candidates SET published_at = created_at")

        pair_columns = self._columns("pairs_seen")
        legacy_pairs = "status" not in pair_columns
        additions = (
            ("status", "TEXT NOT NULL DEFAULT 'done'"),
            ("attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("error", "TEXT"),
            ("result", "TEXT"),
            ("candidate_id", "TEXT"),
            ("retryable", "INTEGER NOT NULL DEFAULT 1"),
            ("new_claim_id", "TEXT"),
            ("other_claim_id", "TEXT"),
            ("finalized_at", "TEXT"),
            ("updated_at", "TEXT"),
        )
        for name, declaration in additions:
            if name not in pair_columns:
                self._connection.execute(f"ALTER TABLE pairs_seen ADD COLUMN {name} {declaration}")
        if legacy_pairs:
            # A pair in the old table had already been classified, so it is done.
            self._connection.execute(
                "UPDATE pairs_seen SET status = 'done', "
                "updated_at = COALESCE(updated_at, seen_at), "
                "finalized_at = COALESCE(finalized_at, seen_at)"
            )

    def _add_claim(self, claim: Claim) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO claims (id, message_id, payload, status) "
                "VALUES (?, ?, ?, ?)",
                (claim.id, claim.message_id, claim.model_dump_json(), str(claim.status)),
            )

    def _active_claims(self) -> list[Claim]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload, status FROM claims WHERE status = 'active'"
            ).fetchall()
        result: list[Claim] = []
        for row in rows:
            claim = Claim.model_validate_json(row["payload"])
            result.append(claim.model_copy(update={"status": ClaimStatus(row["status"])}))
        return result

    def _claim_by_id(self, claim_id: str) -> Claim | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload, status FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
        if row is None:
            return None
        return Claim.model_validate_json(row["payload"]).model_copy(
            update={"status": ClaimStatus(row["status"])}
        )

    def _set_status(self, claim_id: str, status: ClaimStatus) -> None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                return
            claim = Claim.model_validate_json(row["payload"]).model_copy(update={"status": status})
            with self._connection:
                self._connection.execute(
                    "UPDATE claims SET payload = ?, status = ? WHERE id = ?",
                    (claim.model_dump_json(), str(status), claim_id),
                )

    def _add_candidate(self, candidate: Candidate) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO candidates (id, payload, created_at) VALUES (?, ?, ?)",
                (candidate.id, candidate.model_dump_json(), candidate.created_at),
            )

    def _is_candidate_published(self, candidate_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT published_at FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        return row is not None and row["published_at"] is not None

    def _mark_candidate_published(self, candidate_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE candidates SET published_at = ? WHERE id = ?",
                (self._now(), candidate_id),
            )

    def _is_processed(self, message_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
            ).fetchone()
        return row is not None

    def _mark_processed(self, message_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
                (message_id, self._now()),
            )

    @staticmethod
    def _pair_from_row(row: sqlite3.Row) -> PairState:
        raw_result = row["result"]
        return PairState(
            pair_id=str(row["pair_id"]),
            status=PairStatus(str(row["status"])),
            attempts=int(row["attempts"]),
            error=row["error"],
            result=json.loads(raw_result) if raw_result else None,
            candidate_id=row["candidate_id"],
            retryable=bool(row["retryable"]),
            new_claim_id=row["new_claim_id"],
            other_claim_id=row["other_claim_id"],
            finalized_at=row["finalized_at"],
            seen_at=str(row["seen_at"]),
        )

    def _pair_state(self, identifier: str) -> PairState | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM pairs_seen WHERE pair_id = ?", (identifier,)
            ).fetchone()
        return None if row is None else self._pair_from_row(row)

    def _ensure_pair(self, identifier: str, new_claim_id: str, other_claim_id: str) -> PairState:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO pairs_seen "
                "(pair_id, seen_at, status, attempts, retryable, new_claim_id, "
                "other_claim_id, updated_at) "
                "VALUES (?, ?, 'pending', 0, 1, ?, ?, ?)",
                (identifier, self._now(), new_claim_id, other_claim_id, self._now()),
            )
            row = self._connection.execute(
                "SELECT * FROM pairs_seen WHERE pair_id = ?", (identifier,)
            ).fetchone()
        assert row is not None
        return self._pair_from_row(row)

    def _begin_pair(self, identifier: str, max_attempts: int) -> PairState | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM pairs_seen WHERE pair_id = ?", (identifier,)
            ).fetchone()
            if row is None:
                return None
            status = PairStatus(str(row["status"]))
            attempts = int(row["attempts"])
            retryable = bool(row["retryable"])
            if status in (PairStatus.DONE, PairStatus.CLASSIFYING):
                return None
            if not retryable or attempts >= max_attempts:
                return None
            self._connection.execute(
                "UPDATE pairs_seen SET status = 'classifying', attempts = ?, error = NULL, "
                "updated_at = ? WHERE pair_id = ?",
                (attempts + 1, self._now(), identifier),
            )
            row = self._connection.execute(
                "SELECT * FROM pairs_seen WHERE pair_id = ?", (identifier,)
            ).fetchone()
        assert row is not None
        return self._pair_from_row(row)

    def _mark_pair_done(
        self, identifier: str, result: dict[str, Any], candidate_id: str | None = None
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE pairs_seen SET status = 'done', result = ?, error = NULL, "
                "candidate_id = COALESCE(?, candidate_id), updated_at = ? WHERE pair_id = ?",
                (json.dumps(result, sort_keys=True), candidate_id, self._now(), identifier),
            )

    def _mark_pair_failed(self, identifier: str, error: str, *, retryable: bool) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE pairs_seen SET status = 'failed', error = ?, retryable = ?, "
                "result = NULL, updated_at = ? WHERE pair_id = ?",
                (error, int(retryable), self._now(), identifier),
            )

    def _mark_pair_action(self, identifier: str, candidate_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE pairs_seen SET candidate_id = ?, updated_at = ? WHERE pair_id = ?",
                (candidate_id, self._now(), identifier),
            )

    def _mark_pairs_finalized(self, new_claim_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE pairs_seen SET finalized_at = ?, updated_at = ? "
                "WHERE new_claim_id = ? AND finalized_at IS NULL",
                (self._now(), self._now(), new_claim_id),
            )

    def _pairs_for_new_claim(self, new_claim_id: str) -> list[PairState]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM pairs_seen WHERE new_claim_id = ? ORDER BY seen_at, pair_id",
                (new_claim_id,),
            ).fetchall()
        return [self._pair_from_row(row) for row in rows]

    def _unfinalized_claim_ids(self) -> list[str]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT DISTINCT new_claim_id FROM pairs_seen "
                "WHERE new_claim_id IS NOT NULL AND finalized_at IS NULL "
                "ORDER BY new_claim_id"
            ).fetchall()
        return [str(row["new_claim_id"]) for row in rows]

    def _resumable_pairs(self, max_attempts: int) -> list[PairState]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM pairs_seen WHERE status IN ('pending', 'failed') "
                "AND retryable = 1 AND attempts < ? AND new_claim_id IS NOT NULL "
                "AND other_claim_id IS NOT NULL ORDER BY seen_at, pair_id",
                (max_attempts,),
            ).fetchall()
        return [self._pair_from_row(row) for row in rows]

    def _recover_interrupted_pairs(self) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE pairs_seen SET status = 'failed', "
                "error = COALESCE(error, 'interrupted before completion'), updated_at = ? "
                "WHERE status = 'classifying'",
                (self._now(),),
            )
        return int(cursor.rowcount)

    def _has_pair(self, identifier: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM pairs_seen WHERE pair_id = ?", (identifier,)
            ).fetchone()
        return row is not None

    def _mark_pair(self, identifier: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO pairs_seen "
                "(pair_id, seen_at, status, attempts, retryable, finalized_at, updated_at) "
                "VALUES (?, ?, 'done', 0, 0, ?, ?)",
                (identifier, self._now(), self._now(), self._now()),
            )

    def _close(self) -> None:
        with self._lock:
            self._connection.close()

    async def _run(self, function: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(function, *args, **kwargs)

    async def add_claim(self, claim: Claim) -> None:
        await self._run(self._add_claim, claim)

    async def active_claims(self) -> list[Claim]:
        return await self._run(self._active_claims)

    async def claim_by_id(self, claim_id: str) -> Claim | None:
        return await self._run(self._claim_by_id, claim_id)

    async def set_status(self, claim_id: str, status: ClaimStatus) -> None:
        await self._run(self._set_status, claim_id, status)

    async def add_candidate(self, candidate: Candidate) -> None:
        await self._run(self._add_candidate, candidate)

    async def is_candidate_published(self, candidate_id: str) -> bool:
        return await self._run(self._is_candidate_published, candidate_id)

    async def mark_candidate_published(self, candidate_id: str) -> None:
        await self._run(self._mark_candidate_published, candidate_id)

    async def is_processed(self, message_id: str) -> bool:
        return await self._run(self._is_processed, message_id)

    async def mark_processed(self, message_id: str) -> None:
        await self._run(self._mark_processed, message_id)

    async def pair_state(self, identifier: str) -> PairState | None:
        return await self._run(self._pair_state, identifier)

    async def ensure_pair(
        self, identifier: str, new_claim_id: str, other_claim_id: str
    ) -> PairState:
        return await self._run(self._ensure_pair, identifier, new_claim_id, other_claim_id)

    async def begin_pair(self, identifier: str, max_attempts: int) -> PairState | None:
        return await self._run(self._begin_pair, identifier, max_attempts)

    async def mark_pair_done(
        self, identifier: str, result: dict[str, Any], candidate_id: str | None = None
    ) -> None:
        await self._run(self._mark_pair_done, identifier, result, candidate_id)

    async def mark_pair_failed(
        self, identifier: str, error: str, *, retryable: bool = True
    ) -> None:
        await self._run(self._mark_pair_failed, identifier, error, retryable=retryable)

    async def mark_pair_action(self, identifier: str, candidate_id: str) -> None:
        await self._run(self._mark_pair_action, identifier, candidate_id)

    async def mark_pairs_finalized(self, new_claim_id: str) -> None:
        await self._run(self._mark_pairs_finalized, new_claim_id)

    async def pairs_for_new_claim(self, new_claim_id: str) -> list[PairState]:
        return await self._run(self._pairs_for_new_claim, new_claim_id)

    async def unfinalized_claim_ids(self) -> list[str]:
        return await self._run(self._unfinalized_claim_ids)

    async def resumable_pairs(self, max_attempts: int) -> list[PairState]:
        return await self._run(self._resumable_pairs, max_attempts)

    async def recover_interrupted_pairs(self) -> int:
        return await self._run(self._recover_interrupted_pairs)

    async def has_pair(self, identifier: str) -> bool:
        return await self._run(self._has_pair, identifier)

    async def mark_pair(self, identifier: str) -> None:
        await self._run(self._mark_pair, identifier)

    async def close(self) -> None:
        await self._run(self._close)
