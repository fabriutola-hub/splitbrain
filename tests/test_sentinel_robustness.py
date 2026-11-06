"""Sentinel robustness: every relevant match, pair states and retries."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from splitbrain import bootstrap
from splitbrain.agents import sentinel as mod
from splitbrain.core.models import Claim, ClaimKind, Message, make_claim_id
from splitbrain.core.packets import decode
from splitbrain.core.store import ClaimStore, PairStatus, pair_id
from splitbrain.llm.cassette import ReplayMiss
from splitbrain.llm.client import LLMClient, LLMResponseError

ROOM_IDS = {
    "sales": "r-sales",
    "engineering": "r-engineering",
    "support": "r-support",
    "finance": "r-finance",
    "other": "r-other",
    "splitbrain-ops": "r-ops",
}


class FakeAgent:
    agent_id = "fake-agent"

    def __init__(self) -> None:
        self.targeted_calls: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []
        self.ops: list[tuple[str, dict[str, Any]]] = []

    async def op(self, name: str, /, **args: Any) -> Any:
        self.ops.append((name, args))
        if name == "list_rooms":
            return [{"room_id": rid, "name": name} for name, rid in ROOM_IDS.items()]
        return {}

    @asynccontextmanager
    async def act_in(self, room_id: str):
        yield self

    async def targeted(
        self,
        room_id: str,
        body: str,
        *,
        target_names: list[str] | None = None,
        target_roles: list[str] | None = None,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        self.targeted_calls.append(
            {
                "room_id": room_id,
                "body": body,
                "target_names": target_names,
                "target_roles": target_roles,
                "thread_id": thread_id,
            }
        )
        return {"event_id": "sw_fake"}

    async def post(self, room_id: str, body: str, thread_id: str | None = None) -> dict[str, str]:
        self.posts.append({"room_id": room_id, "body": body, "thread_id": thread_id})
        return {"event_id": "sw_fake"}

    async def aclose(self) -> None:
        return None


class FlakyTransport:
    """Fail exactly one model call with a retryable HTTP 503."""

    def __init__(self, replies: list[dict[str, Any]], *, fail_on: int) -> None:
        self.replies = list(replies)
        self.fail_on = fail_on
        self.calls: list[tuple[str, str]] = []

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        if len(self.calls) == self.fail_on:
            raise LLMResponseError("LLM chat/completions failed with HTTP 503: busy")
        if not self.replies:
            raise AssertionError("fake LLM ran out of prepared replies")
        return self.replies.pop(0)

    async def aclose(self) -> None:
        return None


def make_state() -> bootstrap.BootstrapState:
    return bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(
                room_id=room_id,
                channel_type="channel_private" if name == "engineering" else "channel_public",
            )
            for name, room_id in ROOM_IDS.items()
        }
    )


def make_sentinel(
    llm: LLMClient,
    store: ClaimStore,
    agent: FakeAgent,
    **kwargs: Any,
) -> mod.Sentinel:
    kwargs.setdefault("retry_backoff_s", 0.0)
    return mod.Sentinel(
        agent=agent,  # type: ignore[arg-type]
        llm=llm,
        store=store,
        state=make_state(),
        batch_window_s=0.0,
        **kwargs,
    )


def message(
    message_id: str = "m-new",
    *,
    room: str = "sales",
    author: str = "maria",
    text: str = "Confirmed with Acme: SSO will be live on December 1.",
) -> Message:
    return Message(
        message_id=message_id,
        room_id=ROOM_IDS[room],
        room_name=room,
        author=author,
        text=text,
    )


def claim(
    identifier: str,
    *,
    room: str,
    author: str,
    ts: int,
    kind: ClaimKind = ClaimKind.COMMITMENT,
    value: str = "live on 2026-12-01",
) -> Claim:
    return Claim(
        id=identifier,
        room_id=ROOM_IDS[room],
        room_name=room,
        message_id=f"m-{identifier}",
        author=author,
        ts=ts,
        text=f"Claim {identifier}",
        kind=kind,
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        value=value,
        polarity="affirm",
        confidence=0.9,
    )


def extraction_reply(item: Message) -> dict[str, Any]:
    return {
        "results": [
            {
                "message_id": item.message_id,
                "claims": [
                    {
                        "kind": "commitment",
                        "subject": "SSO",
                        "subject_key": "sso",
                        "scope": "Acme",
                        "scope_key": "acme",
                        "value": "live on 2026-12-01",
                        "polarity": "affirm",
                        "effective_date": "2026-12-01",
                        "confidence": 0.95,
                    }
                ],
            }
        ]
    }


def classification(relation: str, confidence: float) -> dict[str, Any]:
    return {
        "relation": relation,
        "confidence": confidence,
        "reason": f"Classified as {relation}.",
    }


async def _seed(store: ClaimStore, *claims: Claim) -> None:
    for item in claims:
        await store.add_claim(item)


async def test_first_compatible_second_contradiction_raises_the_second(
    llm_factory, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    new_message = message()
    compatible = claim("clm_compatible", room="engineering", author="tomas", ts=200)
    contradiction = claim("clm_contradiction", room="support", author="lucia", ts=100)
    llm, transport, _, _ = llm_factory(
        [
            extraction_reply(new_message),
            classification("compatible", 0.95),
            classification("contradiction", 0.92),
        ],
        mode="live",
    )
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, compatible, contradiction)
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    caplog.set_level(logging.INFO)
    await sentinel.start()
    try:
        await sentinel.analyze_messages([new_message])

        assert sentinel.candidates_sent == 1
        assert len(agent.targeted_calls) == 1
        kind, data = decode(agent.targeted_calls[0]["body"].splitlines()[-1])
        assert kind == "candidate"
        assert data["claim_a"]["id"] == "clm_contradiction"
        assert data["confidence"] == pytest.approx(0.92)
        assert len(transport.calls) == 3
        assert "Also matched #engineering tomas (SSO): compatible (0.95)" in caplog.text
    finally:
        await sentinel.aclose()


async def test_two_contradictions_choose_the_highest_confidence(
    llm_factory, tmp_path: Path
) -> None:
    new_message = message()
    recent_low = claim("clm_recent_low", room="engineering", author="tomas", ts=300)
    older_high = claim("clm_older_high", room="support", author="lucia", ts=100)
    llm, _, _, _ = llm_factory(
        [
            extraction_reply(new_message),
            classification("contradiction", 0.81),
            classification("contradiction", 0.96),
        ],
        mode="live",
    )
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, recent_low, older_high)
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    await sentinel.start()
    try:
        await sentinel.analyze_messages([new_message])

        assert sentinel.candidates_sent == 1
        kind, data = decode(agent.targeted_calls[0]["body"].splitlines()[-1])
        assert kind == "candidate"
        assert data["claim_a"]["id"] == "clm_older_high"
        assert data["confidence"] == pytest.approx(0.96)
    finally:
        await sentinel.aclose()


async def test_equal_confidence_contradictions_choose_the_most_recent(
    llm_factory, tmp_path: Path
) -> None:
    new_message = message()
    older = claim("clm_older", room="engineering", author="tomas", ts=100)
    recent = claim("clm_recent", room="support", author="lucia", ts=300)
    llm, _, _, _ = llm_factory(
        [
            extraction_reply(new_message),
            classification("contradiction", 0.9),
            classification("contradiction", 0.9),
        ],
        mode="live",
    )
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, older, recent)
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    await sentinel.start()
    try:
        await sentinel.analyze_messages([new_message])

        assert sentinel.candidates_sent == 1
        _, data = decode(agent.targeted_calls[0]["body"].splitlines()[-1])
        assert data["claim_a"]["id"] == "clm_recent"
    finally:
        await sentinel.aclose()


async def test_at_most_three_matches_are_classified_per_new_claim(
    llm_factory, tmp_path: Path
) -> None:
    new_message = message()
    stored = [
        claim("clm_1", room="engineering", author="tomas", ts=400),
        claim("clm_2", room="support", author="lucia", ts=300),
        claim("clm_3", room="finance", author="pablo", ts=200),
        claim("clm_4", room="other", author="ana", ts=100),
    ]
    llm, transport, _, _ = llm_factory(
        [
            extraction_reply(new_message),
            classification("compatible", 0.9),
            classification("compatible", 0.9),
            classification("compatible", 0.9),
        ],
        mode="live",
    )
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, *stored)
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    await sentinel.start()
    try:
        await sentinel.analyze_messages([new_message])

        assert len(transport.calls) == 4  # one extraction + three classifications
        assert sentinel.candidates_sent == 0
        assert agent.targeted_calls == []
    finally:
        await sentinel.aclose()


async def test_transient_model_failure_is_retried_and_raises_one_candidate(
    llm_factory, tmp_path: Path
) -> None:
    new_message = message()
    other = claim("clm_other", room="engineering", author="tomas", ts=100)
    llm, _, cassettes, settings = llm_factory([], mode="live")
    transport = FlakyTransport(
        [extraction_reply(new_message), classification("contradiction", 0.94)],
        fail_on=2,
    )
    llm = LLMClient(settings, cassettes, transport=transport)
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, other)
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    await sentinel.start()
    try:
        await sentinel.analyze_messages([new_message])

        assert sentinel.candidates_sent == 1
        assert len(agent.targeted_calls) == 1
        assert len(transport.calls) == 3  # extraction, failed classification, retry
        states = await store.pairs_for_new_claim(make_claim_id(new_message.message_id, 0))
        assert len(states) == 1
        assert states[0].status is PairStatus.DONE
        assert states[0].attempts == 2
    finally:
        await sentinel.aclose()


async def test_duplicate_event_does_not_send_a_second_candidate(
    llm_factory, tmp_path: Path
) -> None:
    new_message = message()
    other = claim("clm_other", room="engineering", author="tomas", ts=100)
    llm, transport, _, _ = llm_factory(
        [extraction_reply(new_message), classification("contradiction", 0.94)],
        mode="live",
    )
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, other)
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    await sentinel.start()
    try:
        await sentinel.analyze_messages([new_message])
        await sentinel.analyze_messages([new_message])

        assert sentinel.candidates_sent == 1
        assert len(agent.targeted_calls) == 1
        assert len(transport.calls) == 2
    finally:
        await sentinel.aclose()


async def test_restart_resumes_a_failed_pair(llm_factory, tmp_path: Path) -> None:
    new_claim = claim("clm_new", room="sales", author="maria", ts=300)
    other = claim("clm_other", room="engineering", author="tomas", ts=100)
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, new_claim, other)
    identifier = pair_id(other, new_claim)
    await store.ensure_pair(identifier, new_claim.id, other.id)
    await store.begin_pair(identifier, 3)
    await store.mark_pair_failed(identifier, "HTTP 503", retryable=True)

    llm, transport, _, _ = llm_factory(
        [classification("contradiction", 0.94)],
        mode="live",
    )
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    await sentinel.start()
    try:
        assert sentinel.candidates_sent == 1
        assert len(agent.targeted_calls) == 1
        assert len(transport.calls) == 1
        state = await store.pair_state(identifier)
        assert state is not None
        assert state.status is PairStatus.DONE
        assert state.attempts == 2
    finally:
        await sentinel.aclose()


async def test_replay_miss_fails_loudly_without_retrying(llm_factory, tmp_path: Path) -> None:
    new_claim = claim("clm_new", room="sales", author="maria", ts=300)
    other = claim("clm_other", room="engineering", author="tomas", ts=100)
    store = ClaimStore(tmp_path / "sentinel.db")
    await _seed(store, new_claim, other)
    identifier = pair_id(other, new_claim)
    await store.ensure_pair(identifier, new_claim.id, other.id)

    llm, _, _, _ = llm_factory([], mode="replay")
    agent = FakeAgent()
    sentinel = make_sentinel(llm, store, agent)
    try:
        with pytest.raises(ReplayMiss):
            await sentinel.resume_pairs()
        state = await store.pair_state(identifier)
        assert state is not None
        assert state.status is PairStatus.FAILED
        assert state.retryable is False
        assert state.attempts == 1
        assert await sentinel.resume_pairs() == 0
    finally:
        await sentinel.aclose()
