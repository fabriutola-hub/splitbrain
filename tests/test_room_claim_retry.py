"""Exercise claim recovery with a fake server behind the real client policy."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_decision_integrity import decided_arbiter, sentinel_for

from splitbrain.core.decision_record import CorrectionJournal, pending_corrections
from splitbrain.switch import client as switch_client
from splitbrain.switch.client import MISSING_ROOM_CONTEXT, SwitchAgent, SwitchOpError

ROOM = "r-conflict"
OP_ARGS = {
    "load_internal_documents": {"ids": ["doc-1"]},
    "create_room_document": {
        "name": "progress",
        "description": "delivery receipts",
        "instructions": "Sentinel only",
        "content": "pending",
    },
    "update_room_document": {"document_id": "doc-1", "content": "posted"},
    "post_message": {"body": "correction", "thread_id": "sw-origin"},
    "send_targeted_message": {"body": "decision", "target_roles": ["verifier"]},
    "assume_role": {"role": "arbiter"},
    "release_role": {},
}


def lost_claim(operation: str) -> SwitchOpError:
    return SwitchOpError(operation, 400, json.dumps({"detail": MISSING_ROOM_CONTEXT}))


class ClaimAgent(SwitchAgent):
    """Model Switch's room guard before effects, and ambiguous failures after them."""

    def __init__(self) -> None:
        super().__init__("http://switch.test", "sentinel", "unit-test-key")
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.completed: list[tuple[str, str, dict[str, Any]]] = []
        self.errors: dict[str, list[BaseException]] = {}
        self.after_effect: BaseException | None = None
        self.connected_room = ""

    async def _request_op(self, name: str, /, *, connection: bool = True, **args: Any) -> Any:
        self.calls.append((name, args))
        errors = self.errors.get(name, [])
        if errors:
            error = errors.pop(0)
            if isinstance(error, SwitchOpError) and switch_client.lost_room_context(error):
                self.connected_room = ""
            raise error
        if name == "connect_to_room":
            self.connected_room = args["room_id"]
            return {"room_id": self.connected_room}
        assert self.connected_room, "the fake must not apply an operation without a room"
        self.completed.append((name, self.connected_room, args))
        if self.after_effect is not None:
            raise self.after_effect
        return {"document_id": "doc-1", "event_id": "sw-1"}


@pytest.fixture
async def agent() -> AsyncIterator[ClaimAgent]:
    agent = ClaimAgent()
    try:
        yield agent
    finally:
        await agent.aclose()


@pytest.fixture
def retry_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []
    real_sleep = asyncio.sleep

    async def sleep(delay: float) -> None:
        waits.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(switch_client.asyncio, "sleep", sleep)
    return waits


@pytest.mark.parametrize("operation", OP_ARGS)
@pytest.mark.parametrize("losses", [1, 2])
async def test_room_operations_reconnect_to_the_same_room_then_succeed_once(
    operation: str, losses: int, agent: ClaimAgent, retry_waits: list[float]
) -> None:
    agent.errors[operation] = [lost_claim(operation) for _ in range(losses)]
    async with agent.act_in(ROOM):
        result = await agent.op(operation, **OP_ARGS[operation])
    assert result["event_id"] == "sw-1"
    assert agent.completed == [(operation, ROOM, OP_ARGS[operation])]
    assert agent.calls == (
        [("connect_to_room", {"room_id": ROOM})]
        + [(operation, OP_ARGS[operation]), ("connect_to_room", {"room_id": ROOM})] * losses
        + [(operation, OP_ARGS[operation])]
    )
    assert len(retry_waits) == losses
    assert all(0.05 <= delay <= 0.15 for delay in retry_waits)


async def test_claim_loss_stops_after_three_attempts_with_the_original_error(
    agent: ClaimAgent, retry_waits: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    errors = [lost_claim("post_message") for _ in range(10)]
    final_error = errors[2]
    agent.errors["post_message"] = errors
    with pytest.raises(SwitchOpError) as error:
        await agent.post(ROOM, "correction")
    assert error.value is final_error
    assert "exhausted after 3 attempts" in error.value.__notes__[0]
    assert "post_message" in error.value.__notes__[0] and ROOM in error.value.__notes__[0]
    assert "exhausted after 3 attempts" in caplog.text
    assert [name for name, _ in agent.calls].count("post_message") == 3
    assert [name for name, _ in agent.calls].count("connect_to_room") == 3
    assert len(retry_waits) == 2
    assert not agent.completed


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (400, '{"detail": "Unknown document"}'),
        (400, '{"detail": "Not connected to a room you can access"}'),
        (400, MISSING_ROOM_CONTEXT),
        (400, json.dumps([MISSING_ROOM_CONTEXT])),
        (403, json.dumps({"detail": MISSING_ROOM_CONTEXT})),
        (409, json.dumps({"detail": MISSING_ROOM_CONTEXT})),
        (500, json.dumps({"detail": MISSING_ROOM_CONTEXT})),
    ],
)
async def test_other_failures_propagate_unchanged_without_reconnecting(
    status: int, body: str, agent: ClaimAgent, retry_waits: list[float]
) -> None:
    failure = SwitchOpError("post_message", status, body)
    agent.errors["post_message"] = [failure]
    with pytest.raises(SwitchOpError) as error:
        await agent.post(ROOM, "correction")
    assert error.value is failure
    assert [name for name, _ in agent.calls] == ["connect_to_room", "post_message"]
    assert not retry_waits and not agent.completed


@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout("response lost"), SwitchOpError("post_message", 500, "failed")]
)
async def test_an_ambiguous_failure_after_publication_never_reposts(
    failure: BaseException, agent: ClaimAgent, retry_waits: list[float]
) -> None:
    agent.after_effect = failure
    with pytest.raises(type(failure)) as error:
        await agent.post(ROOM, "correction", thread_id="sw-origin")
    assert error.value is failure
    assert agent.completed == [
        ("post_message", ROOM, {"body": "correction", "thread_id": "sw-origin"})
    ]
    assert [name for name, _ in agent.calls] == ["connect_to_room", "post_message"]
    assert not retry_waits


async def test_retrying_a_save_does_not_repeat_earlier_creations_or_messages(
    agent: ClaimAgent, retry_waits: list[float]
) -> None:
    agent.errors["update_room_document"] = [lost_claim("update_room_document")] * 2
    operations = [
        "create_room_document",
        "post_message",
        "send_targeted_message",
        "update_room_document",
    ]
    async with agent.act_in(ROOM):
        for operation in operations:
            await agent.op(operation, **OP_ARGS[operation])
    assert agent.completed == [(name, ROOM, OP_ARGS[name]) for name in operations]
    assert len(retry_waits) == 2


async def test_post_and_targeted_keep_their_rooms_when_serialized_with_retries(
    agent: ClaimAgent, retry_waits: list[float]
) -> None:
    agent.errors["post_message"] = [lost_claim("post_message")]
    agent.errors["send_targeted_message"] = [lost_claim("send_targeted_message")]
    await asyncio.gather(
        agent.post("r-sales", "correction", thread_id="sw-origin"),
        agent.targeted("r-ops", "decision", target_roles=["verifier"]),
    )
    assert agent.completed == [
        ("post_message", "r-sales", {"body": "correction", "thread_id": "sw-origin"}),
        ("send_targeted_message", "r-ops", {"body": "decision", "target_roles": ["verifier"]}),
    ]
    assert len(retry_waits) == 2


@pytest.mark.parametrize("scope", ["outside", "child-task", "without-connection", "unknown-op"])
async def test_recovery_requires_a_known_operation_and_the_callers_own_room_scope(
    scope: str, agent: ClaimAgent, retry_waits: list[float]
) -> None:
    operation = "unreviewed_operation" if scope == "unknown-op" else "post_message"
    failure = lost_claim(operation)
    agent.errors[operation] = [failure]
    if scope == "outside":
        await agent.op("connect_to_room", room_id=ROOM)
        with pytest.raises(SwitchOpError) as error:
            await agent.op(operation, body="correction")
    else:
        async with agent.act_in(ROOM):
            call = agent.op(operation, connection=scope != "without-connection", body="correction")
            with pytest.raises(SwitchOpError) as error:
                await (asyncio.create_task(call) if scope == "child-task" else call)
    assert error.value is failure
    assert [name for name, _ in agent.calls] == ["connect_to_room", operation]
    assert not retry_waits


async def test_a_failed_reconnect_propagates_without_repeating_the_operation(
    agent: ClaimAgent, retry_waits: list[float]
) -> None:
    failure = SwitchOpError("connect_to_room", 403, "no longer a member")
    async with agent.act_in(ROOM):
        agent.errors["post_message"] = [lost_claim("post_message")]
        agent.errors["connect_to_room"] = [failure]
        with pytest.raises(SwitchOpError) as error:
            await agent.op("post_message", body="correction")
    assert error.value is failure
    assert [name for name, _ in agent.calls] == [
        "connect_to_room",
        "post_message",
        "connect_to_room",
    ]
    assert not agent.completed and len(retry_waits) == 1


async def test_cancellation_during_backoff_releases_the_room_scope(
    agent: ClaimAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def cancel(delay: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(switch_client.asyncio, "sleep", cancel)
    agent.errors["post_message"] = [lost_claim("post_message")]
    with pytest.raises(asyncio.CancelledError):
        await agent.post(ROOM, "correction")
    assert [name for name, _ in agent.calls] == ["connect_to_room", "post_message"]
    # An unscoped call after cancellation must not inherit the abandoned room.
    agent.errors["post_message"] = [lost_claim("post_message")]
    with pytest.raises(SwitchOpError):
        await agent.op("post_message", body="correction")
    await asyncio.wait_for(agent.post("r-other", "next"), timeout=1)
    assert agent.completed == [("post_message", "r-other", {"body": "next"})]


@pytest.mark.parametrize("document_id", ["", "doc-1"])
@pytest.mark.parametrize("losses", [1, 2])
async def test_save_corrections_survives_lost_claims_without_duplicate_documents(
    document_id: str,
    losses: int,
    agent: ClaimAgent,
    retry_waits: list[float],
    tmp_path: Path,
    llm_factory: Any,
) -> None:
    _, _, _, packet = await decided_arbiter()
    journal = CorrectionJournal(decided=packet, threads=pending_corrections(packet.origins))
    operation = "update_room_document" if document_id else "create_room_document"
    agent.errors[operation] = [lost_claim(operation) for _ in range(losses)]
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    try:
        assert await sentinel._save_corrections(document_id, journal) == "doc-1"
    finally:
        await sentinel.aclose()
    assert len(agent.completed) == 1
    name, room_id, args = agent.completed[0]
    assert name == operation and room_id == journal.decided.conflict_room
    assert args["content"] == journal.render()
    assert len(retry_waits) == losses
