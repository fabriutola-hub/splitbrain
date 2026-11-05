"""SQLite persistence for the Sentinel.

Plain sqlite3 from the standard library. Sync statements run in a worker thread so
the agent's event loop never blocks on disk.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from datetime import UTC, datetime
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
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pairs_seen (
    pair_id TEXT PRIMARY KEY,
    seen_at TEXT NOT NULL
);
"""


def pair_id(claim_a: Claim, claim_b: Claim) -> str:
    return "|".join(sorted((claim_a.id, claim_b.id)))


class ClaimStore:
    def __init__(self, path: Path | str = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._connection.executescript(_SCHEMA)
            self._connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _add_claim(self, claim: Claim) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO claims (id, message_id, payload, status) "
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
                "INSERT OR REPLACE INTO candidates (id, payload, created_at) VALUES (?, ?, ?)",
                (candidate.id, candidate.model_dump_json(), candidate.created_at),
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

    def _has_pair(self, identifier: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM pairs_seen WHERE pair_id = ?", (identifier,)
            ).fetchone()
        return row is not None

    def _mark_pair(self, identifier: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO pairs_seen (pair_id, seen_at) VALUES (?, ?)",
                (identifier, self._now()),
            )

    def _close(self) -> None:
        with self._lock:
            self._connection.close()

    async def _run(self, function: Any, *args: Any) -> Any:
        return await asyncio.to_thread(function, *args)

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

    async def is_processed(self, message_id: str) -> bool:
        return await self._run(self._is_processed, message_id)

    async def mark_processed(self, message_id: str) -> None:
        await self._run(self._mark_processed, message_id)

    async def has_pair(self, identifier: str) -> bool:
        return await self._run(self._has_pair, identifier)

    async def mark_pair(self, identifier: str) -> None:
        await self._run(self._mark_pair, identifier)

    async def close(self) -> None:
        await self._run(self._close)
