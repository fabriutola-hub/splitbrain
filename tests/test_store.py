"""SQLite store: idempotency, statuses, candidates and pairs_seen."""

from __future__ import annotations

from pathlib import Path

from splitbrain.core.models import Candidate, Claim, ClaimStatus, Relation
from splitbrain.core.store import ClaimStore, pair_id


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
