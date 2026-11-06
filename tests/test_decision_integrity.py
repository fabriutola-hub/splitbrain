"""Decision integrity across delayed events, holder changes and partial delivery."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from decision_fakes import FakeSwitch

from splitbrain import bootstrap
from splitbrain.agents.arbiter import AGENT_NAME, STANDBY_NAME, Arbiter, Verification
from splitbrain.agents.sentinel import Sentinel
from splitbrain.config import SplitbrainError
from splitbrain.core.decision import DecisionMachine, DecisionState
from splitbrain.core.decision_record import (
    latest_record,
    load_correction_journal,
    load_decision_records,
)
from splitbrain.core.packets import encode
from splitbrain.core.protocol import CandidatePacket, DecidedPacket, OriginRef, PacketClaim
from splitbrain.core.store import ClaimStore
from splitbrain.switch.events import MessageFrame, MessagePayload

ROOM = "r-conflict"
CONFLICT = "sb-0001"


def arbiter_for(agent: FakeSwitch) -> Arbiter:
    arbiter = Arbiter(
        agent=agent,  # type: ignore[arg-type]
        state=bootstrap.BootstrapState(
            rooms={
                "splitbrain-ops": bootstrap.RoomState(
                    room_id="r-ops", channel_type="channel_private"
                )
            }
        ),
        name=agent.name,
        consent_timeout_s=600,
        evidence_timeout_s=60,
    )
    arbiter.is_holder = True
    arbiter.coverage.rooms[ROOM] = "conflict-sb-0001-sso"
    return arbiter


async def open_arbiter() -> tuple[Arbiter, Verification, FakeSwitch]:
    agent = FakeSwitch(AGENT_NAME)
    agent.state.add_origin("r-ops", "sw-candidate")
    claims = [
        PacketClaim(
            id=f"clm_{author}",
            room_id=f"r-{room}",
            room_name=room,
            message_id=f"sw_{author}",
            author=author,
            subject="SSO",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            text="A promise",
        )
        for author, room in [("maria", "sales"), ("tomas", "engineering")]
    ]
    candidate = CandidatePacket(id=CONFLICT, claim_a=claims[0], claim_b=claims[1])
    item = Verification(
        candidate=candidate,
        thread_id="sw-candidate",
        requested_at=0,
        room_id=ROOM,
        room_name="conflict-sb-0001-sso",
        machine=DecisionMachine("maria", "tomas", conflict_id=CONFLICT),
        origins=[
            OriginRef(
                room_id=claim.room_id,
                room_name=claim.room_name,
                thread_id=claim.thread_root,
                message_id=claim.message_id,
                claim_id=claim.id,
                author=claim.author,
            )
            for claim in claims
        ],
    )
    for origin in item.origins:
        agent.state.add_origin(origin.room_id, origin.thread_id)
    arbiter = arbiter_for(agent)
    item.record = arbiter._open_record(item)
    arbiter.verifications[CONFLICT] = item
    arbiter.by_room[ROOM] = CONFLICT
    await arbiter._save_record(item)
    return arbiter, item, agent


def human(
    author: str,
    text: str,
    *,
    ident: str = "sw-confirm",
    ts: int = 3000,
    thread: str | None = None,
    kind: str | None = "user",
) -> MessageFrame:
    return MessageFrame(
        sequence=ts,
        room_id=ROOM,
        payload=MessagePayload(
            sender_name=author,
            sender_kind=kind,
            body=text,
            message_id=ident,
            timestamp=ts,
            thread_id=thread,
        ),
    )


async def propose(arbiter: Arbiter, version: int = 1) -> None:
    await arbiter.on_frame(
        human(
            "maria",
            f"decision: SSO in Q{version}",
            ident=f"sw-proposal-{version}",
            ts=1000 * version,
        )
    )


async def decided_arbiter() -> tuple[Arbiter, Verification, FakeSwitch, DecidedPacket]:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    await arbiter.on_frame(human("tomas", "confirm"))
    return arbiter, item, agent, arbiter._decision_packet(item)


@pytest.mark.parametrize(
    ("author", "kind"),
    [("lucia", "user"), ("splitbrain-verifier", "agent"), ("maria", "user"), ("tomas", "agent")],
)
async def test_only_the_other_human_owner_can_confirm(author: str, kind: str) -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    await arbiter.on_frame(human(author, "confirm", kind=kind))
    assert item.machine.state == DecisionState.PROPOSED
    assert not item.machine.confirmations
    assert not item.decided
    assert not agent.targeted_calls


@pytest.mark.parametrize(
    "text",
    [
        "yes, but…",
        "sí, si legal aprueba",
        "ok, lo revisamos mañana",
        "confirmed if legal approves",
        "confirm unless it slips",
        "agreed pending approval",
        "yes once approved",
        "ok after the meeting",
        "sounds good tomorrow",
        "confirmed later",
        "yes maybe",
        "confirm?",
        "¿de acuerdo?",
        "sí, pero falta legal",
        "confirmo cuando aprueben",
        "ok luego",
        "de acuerdo, depende de legal",
        "sí, a menos que lo cancelen",
    ],
)
async def test_conditional_or_uncertain_confirmation_explains_why_it_stays_open(text: str) -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    await arbiter.on_frame(human("tomas", text))
    assert item.machine.state == DecisionState.PROPOSED
    assert not item.machine.confirmations
    assert "v1 is still open" in agent.posts[-1]["body"]
    assert "Reply confirm when it is final" in agent.posts[-1]["body"]
    assert not agent.targeted_calls


@pytest.mark.parametrize(
    "text", ["confirm", "Confirmed, thanks!", "agreed", "sounds good", "de acuerdo", "👍", "✅"]
)
async def test_unconditional_natural_confirmation_records_the_current_version(text: str) -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    await arbiter.on_frame(human("tomas", text))
    assert item.machine.state == DecisionState.DECIDED
    assert item.machine.confirmations[0].version == 1
    assert item.machine.confirmations[0].message_id == "sw-confirm"
    assert item.machine.confirmations[0].timestamp == 3000
    assert len(agent.targeted_calls) == 1
    records, _ = await load_decision_records(agent, ROOM, CONFLICT)
    saved = latest_record(records).state
    assert saved.machine.confirmations == item.machine.confirmations
    assert saved.machine.state == DecisionState.DECIDED
    assert all(progress.status == "pending" for progress in saved.corrections)


async def test_new_proposal_invalidates_old_version_and_delayed_thread_confirmations() -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    old_announcement = agent.posts[-1]["id"]
    await arbiter.on_frame(human("tomas", "yes, but legal", ident="conditional", ts=1500))
    await propose(arbiter, 2)
    assert item.machine.version == 2
    assert item.machine.confirmed_by is None
    assert not item.machine.confirmations
    for index, (text, thread) in enumerate(
        [
            ("confirm", "sw-proposal-1"),
            ("Confirmed, thanks!", old_announcement),
            ("confirm sb-0001 v1", None),
            ("confirm v1", None),
            ("confirm sb-9999 v2", None),
            ("confirm sb-0001 v2", old_announcement),
        ]
    ):
        await arbiter.on_frame(human("tomas", text, thread=thread, ident=f"old-{index}"))
        assert item.machine.state == DecisionState.PROPOSED
        assert "still open" in agent.posts[-1]["body"]
    # An explicit reference proves the intended version even with a stale clock.
    await arbiter.on_frame(human("tomas", "confirm sb-0001 v2", ts=500))
    assert item.decided
    assert item.machine.decision == "SSO in Q2"
    assert [proposal.version for proposal in item.machine.proposals] == [1, 2]
    assert [confirmation.version for confirmation in item.machine.confirmations] == [2]


@pytest.mark.parametrize("timestamp", [0, 500, 1000])
async def test_unthreaded_confirmation_needs_a_timestamp_after_the_proposal(timestamp: int) -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    await arbiter.on_frame(human("tomas", "confirm", ts=timestamp))
    assert not item.decided
    assert "cannot tie that reply to v1" in agent.posts[-1]["body"]
    assert "confirm sb-0001 v1" in agent.posts[-1]["body"]


@pytest.mark.parametrize("reply_to_announcement", [False, True])
async def test_current_proposal_thread_proves_the_version_without_a_clock(
    reply_to_announcement: bool,
) -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    thread = agent.posts[-1]["id"] if reply_to_announcement else "sw-proposal-1"
    await arbiter.on_frame(human("tomas", "confirm", thread=thread, ts=0))
    assert item.decided


async def test_duplicate_proposal_and_confirmation_events_do_not_repeat_the_decision() -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    await propose(arbiter)
    assert item.machine.version == 1
    assert len(agent.posts) == 1
    await arbiter.on_frame(human("tomas", "confirm"))
    await arbiter.on_frame(human("tomas", "confirm"))
    assert len(item.machine.confirmations) == 1
    assert sum(post["body"].startswith("Decision recorded:") for post in agent.posts) == 1
    assert len(agent.targeted_calls) == 1


async def test_standby_recovers_decided_document_and_never_reopens_it() -> None:
    _, original, primary, _ = await decided_arbiter()
    original_content = primary.state.documents[original.document_id]["content"]
    standby_agent = FakeSwitch(STANDBY_NAME, primary.state)
    standby = arbiter_for(standby_agent)
    standby.coverage.rooms.pop(ROOM)
    await standby._ensure_role()
    adopted = standby.verifications[CONFLICT]
    assert adopted.decided
    assert adopted.machine.snapshot() == original.machine.snapshot()
    assert adopted.document_id != original.document_id
    assert primary.state.documents[original.document_id]["content"] == original_content
    await standby.on_frame(human("maria", "decision: Different text", ident="new", ts=4000))
    await standby.on_frame(human("tomas", "confirm", ident="repeated", ts=5000))
    assert adopted.machine.state == DecisionState.DECIDED
    assert adopted.machine.decision == "SSO in Q1"
    assert not standby_agent.posts
    # A primary coming back selects the final recovery snapshot as well.
    recovered = arbiter_for(FakeSwitch(AGENT_NAME, primary.state))
    primary.state.holders = [AGENT_NAME]
    await recovered._ensure_role()
    assert recovered.verifications[CONFLICT].machine.state == DecisionState.DECIDED


async def test_standby_recovers_open_v2_and_a_later_confirmation_closes_it() -> None:
    arbiter, item, primary = await open_arbiter()
    await propose(arbiter)
    await propose(arbiter, 2)
    standby_agent = FakeSwitch(STANDBY_NAME, primary.state)
    standby = arbiter_for(standby_agent)
    await standby._ensure_role()
    adopted = standby.verifications[CONFLICT]
    assert adopted.machine.version == 2
    assert adopted.machine.proposals == item.machine.proposals
    assert not adopted.decided
    await standby.on_frame(human("tomas", "confirm", thread="sw-proposal-1"))
    assert not adopted.decided
    await standby.on_frame(human("tomas", "Confirmed, thanks!", ident="current", ts=4000))
    assert adopted.decided
    assert adopted.machine.confirmations[-1].version == 2
    assert primary.state.documents[adopted.document_id]["owner"] == STANDBY_NAME
    # A process that loses and regains the lease must also refresh its cached OPEN state.
    arbiter.is_holder = False
    primary.state.holders = [AGENT_NAME]
    await arbiter._ensure_role()
    assert arbiter.verifications[CONFLICT].decided
    assert arbiter.verifications[CONFLICT].machine.confirmations[-1].version == 2


def decision_frame(packet: DecidedPacket) -> MessageFrame:
    return MessageFrame(
        sequence=10,
        room_id="r-ops",
        payload=MessagePayload(
            sender_name=AGENT_NAME,
            message_id="sw-decided",
            thread_id="sw-candidate",
            body=encode("decided", packet),
        ),
    )


def sentinel_for(agent: FakeSwitch, llm_factory: Any, path: Path) -> Sentinel:
    llm, _, _, _ = llm_factory([], mode="live")
    return Sentinel(
        agent=agent,  # type: ignore[arg-type]
        llm=llm,
        store=ClaimStore(path / "sentinel.db"),
        state=bootstrap.BootstrapState(
            rooms={
                "splitbrain-ops": bootstrap.RoomState(
                    room_id="r-ops", channel_type="channel_private"
                ),
                "sales": bootstrap.RoomState(room_id="r-sales", channel_type="channel_public"),
                "engineering": bootstrap.RoomState(
                    room_id="r-engineering", channel_type="channel_private"
                ),
            }
        ),
    )


@pytest.mark.parametrize("failure", ["second_post", "lost_response", "lost_checkpoint"])
async def test_restart_resumes_only_missing_corrections(
    failure: str, tmp_path: Path, llm_factory: Any
) -> None:
    arbiter, item, primary, packet = await decided_arbiter()
    failed_agent = FakeSwitch("splitbrain-sentinel", primary.state)
    if failure == "second_post":
        failed_agent.fail_before_room = "r-engineering"
    elif failure == "lost_response":
        failed_agent.fail_after_room = "r-sales"
    else:
        failed_agent.fail_checkpoint_after_post = True
    first = sentinel_for(failed_agent, llm_factory, tmp_path)
    try:
        with pytest.raises(RuntimeError):
            await first.on_frame(decision_frame(packet))
        assert CONFLICT not in first.corrected
        _, progress = await load_correction_journal(failed_agent, ROOM, CONFLICT)
        assert not progress.complete
        assert progress.threads[0].status == ("posted" if failure == "second_post" else "pending")
        assert len(failed_agent.posts) == 1
    finally:
        await first.aclose()
    restarted_agent = FakeSwitch("splitbrain-sentinel", primary.state)
    restarted = sentinel_for(restarted_agent, llm_factory, tmp_path)
    try:
        await restarted.on_frame(decision_frame(packet))
        assert [post["room_id"] for post in restarted_agent.posts] == ["r-engineering"]
        _, progress = await load_correction_journal(restarted_agent, ROOM, CONFLICT)
        assert progress.complete and progress.notified
        assert all(thread.message_id for thread in progress.threads)
        assert len({thread.message_id for thread in progress.threads}) == 2
        assert CONFLICT in restarted.corrected
        assert len(await restarted.store.active_claims()) == 1
        await restarted.on_frame(decision_frame(packet))
        assert len(restarted_agent.posts) == 1
        assert len(restarted_agent.targeted_calls) == 1
        # The Arbiter can recover completion even if sb:corrected was missed.
        await arbiter._publish_decision(item, retry=True)
        assert item.corrected
        assert all(thread.status == "posted" for thread in item.durable.corrections)
        assert "Corrections posted in #sales, #engineering" in item.record
    finally:
        await restarted.aclose()


async def test_concurrent_duplicate_decided_events_publish_each_correction_once(
    tmp_path: Path, llm_factory: Any
) -> None:
    _, _, primary, packet = await decided_arbiter()
    agent = FakeSwitch("splitbrain-sentinel", primary.state)
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    try:
        await asyncio.gather(
            sentinel.on_frame(decision_frame(packet)), sentinel.on_frame(decision_frame(packet))
        )
        assert len(agent.posts) == 2
        assert len(agent.targeted_calls) == 1
    finally:
        await sentinel.aclose()
    next_agent = FakeSwitch("splitbrain-sentinel", primary.state)
    next_sentinel = sentinel_for(next_agent, llm_factory, tmp_path)
    try:
        await next_sentinel.on_frame(decision_frame(packet))
        assert not next_agent.posts
        assert not next_agent.targeted_calls
    finally:
        await next_sentinel.aclose()


async def test_missing_origin_history_keeps_correction_pending(
    tmp_path: Path, llm_factory: Any
) -> None:
    _, _, primary, packet = await decided_arbiter()
    primary.state.threads["r-sales"] = []
    agent = FakeSwitch("splitbrain-sentinel", primary.state)
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    try:
        with pytest.raises(SplitbrainError, match="outside Switch context"):
            await sentinel.on_frame(decision_frame(packet))
        assert not agent.posts
        assert CONFLICT not in sentinel.corrected
        _, progress = await load_correction_journal(agent, ROOM, CONFLICT)
        assert all(thread.status == "pending" for thread in progress.threads)
    finally:
        await sentinel.aclose()


@pytest.mark.parametrize("failure", ["lost_response", "lost_checkpoint"])
async def test_recovery_finds_the_posted_proposal_announcement_without_duplicating_it(
    failure: str,
) -> None:
    arbiter, _, primary = await open_arbiter()
    if failure == "lost_response":
        primary.fail_after_room = ROOM
    else:
        primary.fail_checkpoint_after_post = True
    with pytest.raises(RuntimeError):
        await propose(arbiter)
    assert len(primary.posts) == 1
    announcement_id = primary.posts[0]["id"]
    standby_agent = FakeSwitch(STANDBY_NAME, primary.state)
    standby = arbiter_for(standby_agent)
    await standby._ensure_role()
    assert not standby_agent.posts
    await standby.on_frame(human("tomas", "confirm", ts=0, thread=announcement_id))
    assert standby.verifications[CONFLICT].decided


async def test_failed_decision_checkpoint_is_retryable_without_duplicate_record_lines() -> None:
    arbiter, item, agent = await open_arbiter()
    await propose(arbiter)
    agent.fail_next_update = True
    with pytest.raises(RuntimeError, match="checkpoint failed"):
        await arbiter.on_frame(human("tomas", "confirm"))
    assert not item.decided
    assert item.machine.state == DecisionState.PROPOSED
    assert not agent.targeted_calls
    await arbiter.on_frame(human("tomas", "confirm"))
    assert item.decided
    assert item.record.count("Decision version: v1") == 1
    assert len(agent.targeted_calls) == 1


async def test_lost_corrected_ack_response_recovers_without_another_publication(
    tmp_path: Path, llm_factory: Any
) -> None:
    arbiter, item, primary, packet = await decided_arbiter()
    failed_agent = FakeSwitch("splitbrain-sentinel", primary.state)
    failed_agent.fail_targeted_after_send = True
    first = sentinel_for(failed_agent, llm_factory, tmp_path)
    try:
        with pytest.raises(RuntimeError, match="targeted response lost"):
            await first.on_frame(decision_frame(packet))
        _, progress = await load_correction_journal(failed_agent, ROOM, CONFLICT)
        assert progress.complete and not progress.notified
        assert CONFLICT not in first.corrected
    finally:
        await first.aclose()
    restarted_agent = FakeSwitch("splitbrain-sentinel", primary.state)
    restarted = sentinel_for(restarted_agent, llm_factory, tmp_path)
    try:
        await restarted.on_frame(decision_frame(packet))
        assert not restarted_agent.posts
        assert not restarted_agent.targeted_calls
        assert CONFLICT in restarted.corrected
        await arbiter._publish_decision(item, retry=True)
        assert item.corrected
    finally:
        await restarted.aclose()


async def test_newer_open_snapshot_cannot_override_a_persisted_final_decision() -> None:
    _, _, primary, _ = await decided_arbiter()
    pending, pending_item, pending_agent = await open_arbiter()
    await propose(pending)
    await propose(pending, 2)
    stale = dict(pending_agent.state.documents[pending_item.document_id])
    stale["id"] = "doc-stale-open"
    primary.state.documents["doc-stale-open"] = stale
    standby = arbiter_for(FakeSwitch(STANDBY_NAME, primary.state))
    await standby._ensure_role()
    adopted = standby.verifications[CONFLICT]
    assert adopted.decided
    assert adopted.machine.decision == "SSO in Q1"
    assert adopted.machine.version == 1
