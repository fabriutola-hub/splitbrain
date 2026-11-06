"""SQLite store: idempotency, statuses, candidates and pairs_seen."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from splitbrain.core.models import Candidate, Claim, ClaimStatus, Relation
from splitbrain.core.store import ClaimStore, PairStatus, pair_id


def claim(identifier: str) -> Claim:
    return Claim(
        id=identifier,
        room_id="sales",
        room_name="sales",
        message_id=f"m-{identifier}",
        author="maria",
        text="Confirmed with Acme SSO for December 1.",
        kind="commitment",
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        value="live on 2026-12-01",
        polarity="affirm",
        confidence=0.9,
    )


async def test_claim_lifecycle_and_status() -> None:
    store = ClaimStore()
    try:
        await store.add_claim(claim("c1"))
        assert [c.id for c in await store.active_claims()] == ["c1"]
        await store.set_status("c1", ClaimStatus.SUPERSEDED)
        assert await store.active_claims() == []
    finally:
        await store.close()


async def test_processed_messages_and_pairs_seen_are_idempotent() -> None:
    store = ClaimStore()
    try:
        assert not await store.is_processed("m1")
        await store.mark_processed("m1")
        await store.mark_processed("m1")
        assert await store.is_processed("m1")
        identifier = pair_id(claim("c1"), claim("c2"))
        assert identifier == "c1|c2"
        assert not await store.has_pair(identifier)
        await store.mark_pair(identifier)
        assert await store.has_pair(identifier)
    finally:
        await store.close()


async def test_candidate_round_trip(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "sentinel.db")
    try:
        await store.add_candidate(
            Candidate(
                id="sb-0001",
                claim_a=claim("c1"),
                claim_b=claim("c2"),
                relation=Relation.CONTRADICTION,
                confidence=0.91,
                reason="Two dates.",
                created_at="2026-11-04T10:00:00+00:00",
            )
        )
    finally:
        await store.close()
    assert (tmp_path / "sentinel.db").is_file()


async def test_pair_state_lifecycle_and_resume() -> None:
    store = ClaimStore()
    try:
        identifier = pair_id(claim("c1"), claim("c2"))
        state = await store.ensure_pair(identifier, "c1", "c2")
        assert state.status is PairStatus.PENDING
        assert state.attempts == 0

        state = await store.begin_pair(identifier, 3)
        assert state is not None
        assert state.status is PairStatus.CLASSIFYING
        assert state.attempts == 1

        await store.mark_pair_failed(identifier, "HTTP 503", retryable=True)
        state = await store.pair_state(identifier)
        assert state is not None
        assert state.status is PairStatus.FAILED
        assert state.retryable is True
        assert [item.pair_id for item in await store.resumable_pairs(3)] == [identifier]

        state = await store.begin_pair(identifier, 3)
        assert state is not None
        assert state.attempts == 2
        await store.mark_pair_done(
            identifier,
            {"relation": "compatible", "confidence": 0.9, "reason": "Same date."},
        )
        state = await store.pair_state(identifier)
        assert state is not None
        assert state.status is PairStatus.DONE
        assert state.result is not None
        assert state.result["relation"] == "compatible"
        assert await store.resumable_pairs(3) == []

        assert await store.unfinalized_claim_ids() == ["c1"]
        await store.mark_pairs_finalized("c1")
        assert await store.unfinalized_claim_ids() == []
    finally:
        await store.close()


async def test_candidate_delivery_is_tracked_once() -> None:
    store = ClaimStore()
    try:
        candidate = Candidate(
            id="sb-0002",
            claim_a=claim("c1"),
            claim_b=claim("c2"),
            relation=Relation.CONTRADICTION,
            confidence=0.91,
            reason="Two dates.",
            created_at="2026-11-04T10:00:00+00:00",
        )
        await store.add_candidate(candidate)
        assert await store.is_candidate_published(candidate.id) is False
        await store.mark_candidate_published(candidate.id)
        assert await store.is_candidate_published(candidate.id) is True
    finally:
        await store.close()


def test_old_pairs_and_candidates_migrate_to_the_new_state(tmp_path: Path) -> None:
    path = tmp_path / "sentinel.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE claims (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE candidates (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE processed_messages (
            message_id TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        );
        CREATE TABLE pairs_seen (
            pair_id TEXT PRIMARY KEY,
            seen_at TEXT NOT NULL
        );
        INSERT INTO pairs_seen (pair_id, seen_at) VALUES ('c1|c2', '2026-11-04T10:00:00+00:00');
        INSERT INTO candidates (id, payload, created_at)
            VALUES ('sb-0001', '{}', '2026-11-04T10:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    store = ClaimStore(path)
    try:
        state = store._pair_state("c1|c2")
        assert state is not None
        assert state.status is PairStatus.DONE
        assert state.finalized_at is not None
        assert store._is_candidate_published("sb-0001") is True
    finally:
        store._close()
