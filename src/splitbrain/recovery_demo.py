"""Observable recovery checks shared by the CLI demo and its integration test."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

from . import bootstrap, demo_faults, seed
from .config import Settings, SplitbrainError
from .core.decision import DecisionState, quoted_sentence
from .core.decision_record import (
    CorrectionJournal,
    DecisionRecord,
    latest_record,
    message_id,
    read_correction_journal,
    read_decision_records,
)
from .switch.client import SwitchAgent, SwitchOpError, transient_switch_error
from .switch.events import ConnectionStateFrame, SwitchFrame
from .switch.mattermost import MattermostUser

if TYPE_CHECKING:
    from .demo import AgentGroup

PRIMARY = "splitbrain-arbiter"
STANDBY = "splitbrain-arbiter-b"
SENTINEL = "splitbrain-sentinel"
POLL_S = 0.5
RECOVERY_TIMEOUT_S = 120.0
DUPLICATE_SETTLE_S = 5.0


class RecoveryObservation(BaseModel):
    rooms: list[str]
    holders: list[str]
    documents: list[str]
    proposals: list[str]
    decisions: list[str]
    decision_senders: list[str]
    decision_matches_proposal: bool
    confirmations: list[str]
    corrections: list[list[str]]
    record: DecisionRecord | None
    journal: CorrectionJournal | None

    def counts(self) -> dict[str, Any]:
        return {
            "rooms": self.rooms,
            "holders": self.holders,
            "documents": self.documents,
            "proposals": len(self.proposals),
            "decisions": len(self.decisions),
            "corrections_per_thread": [len(items) for items in self.corrections],
            "version": self.record.machine.version if self.record else None,
            "state": self.record.machine.state if self.record else None,
        }


class RecoveryReport(BaseModel):
    room_name: str
    room_id: str
    canonical_document_id: str
    recovery_document_ids: list[str]
    proposal_version: int = 1
    adopted_author: str
    adopted_confirmations: int = 0
    decision_sender: str
    sentinel_exit_code: int
    checkpoint_statuses: list[str]
    decision_count: int
    correction_counts: list[int]
    room_count: int
    repeated_confirmations: int

    def print_summary(self) -> None:
        print("\nRECOVERY SUMMARY", flush=True)
        print(
            f"Arbiter takeover:  primary stopped after proposal v{self.proposal_version}; "
            f"arbiter-b adopted #{self.room_name} from the room document and recorded the decision "
            "(same room, same proposal; it writes its own takeover snapshot because Switch "
            "only lets a document's creator edit it)",
            flush=True,
        )
        print(
            "Sentinel restart:  exited after 1 of 2 corrections; restarted; posted the missing "
            "one; each thread has exactly 1 correction",
            flush=True,
        )
        print(
            "Duplicate event:   repeated confirmation ignored; still 1 decision, 2 corrections, "
            "1 room",
            flush=True,
        )
        print(
            f"Room documents:   canonical {self.canonical_document_id} preserved; "
            f"{len(self.recovery_document_ids)} standby-owned recovery snapshot(s)",
            flush=True,
        )


async def wait_for_observation[T](
    group: AgentGroup,
    description: str,
    poll: Callable[[], Awaitable[T]],
    ready: Callable[[T], bool],
    *,
    timeout_s: float = RECOVERY_TIMEOUT_S,
) -> T:
    deadline = time.monotonic() + timeout_s
    while True:
        group.check()
        try:
            observed = await poll()
        except (SwitchOpError, httpx.TransportError) as exc:
            if not transient_switch_error(exc):
                raise
            if time.monotonic() >= deadline:
                raise SplitbrainError(
                    f"Recovery expected {description}; observed a transient Switch read "
                    f"error until the timeout: {exc}"
                ) from None
            await asyncio.sleep(POLL_S)
            continue
        if ready(observed):
            return observed
        if time.monotonic() >= deadline:
            detail = observed.counts() if isinstance(observed, RecoveryObservation) else observed
            raise SplitbrainError(f"Recovery expected {description}; observed {detail!r}")
        await asyncio.sleep(POLL_S)


def require_equal(description: str, expected: Any, observed: Any) -> None:
    if observed != expected:
        raise SplitbrainError(
            f"Recovery expected {description}: {expected!r}; observed {observed!r}"
        )


def context_messages(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for thread in context.get("threads", [])
        for entry in [thread.get("root") or {}, *(thread.get("replies") or [])]
    ]


class RecoveryDemo:
    def __init__(
        self,
        settings: Settings,
        state: bootstrap.BootstrapState,
        group: AgentGroup,
        observer: SwitchAgent,
        root: Path,
        env: dict[str, str],
        decision: seed.SeedDecision,
    ) -> None:
        self.settings = settings
        self.state = state
        self.group = group
        self.observer = observer
        self.root = root
        self.env = env
        self.decision = decision
        self.room_id = ""
        self.room_name = ""
        self.candidate_id = ""
        self.existing_rooms: set[str] = set()
        self.proposed: RecoveryObservation | None = None
        self.report: RecoveryReport | None = None
        self.stream: asyncio.Task[None] | None = None
        self.stream_stop = asyncio.Event()

    async def start(self) -> None:
        ready = asyncio.Event()

        async def on_frame(frame: SwitchFrame) -> None:
            if isinstance(frame, ConnectionStateFrame):
                ready.set()

        self.stream = asyncio.create_task(
            self.observer.run(on_frame, stop=self.stream_stop), name="recovery-observer"
        )
        waiter = asyncio.create_task(ready.wait())
        try:
            done, _ = await asyncio.wait(
                {self.stream, waiter}, timeout=30.0, return_when=asyncio.FIRST_COMPLETED
            )
            if self.stream in done:
                await self.stream
                raise SplitbrainError("Recovery observer exited before its stream was ready")
            if waiter not in done:
                raise SplitbrainError("Recovery expected an observer stream within 30s")
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
        self.existing_rooms = set(await self._rooms())
        self.group.child("sentinel").expected_returncode = demo_faults.EXIT_CODE

    async def aclose(self) -> None:
        self.stream_stop.set()
        if self.stream is not None:
            self.stream.cancel()
            await asyncio.gather(self.stream, return_exceptions=True)

    async def _rooms(self) -> list[str]:
        rooms = await self.observer.op("list_all_rooms", connection=False)
        entries = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
        return sorted(
            str(item["room_id"])
            for item in entries
            if str(item.get("name", "")).startswith("conflict-")
        )

    async def observe(self) -> RecoveryObservation:
        if self.stream is not None and self.stream.done():
            await self.stream
            raise SplitbrainError("Recovery observer stream exited during verification")
        rooms = sorted(set(await self._rooms()) - self.existing_rooms)
        detail = await self.observer.op(
            "get_room_detail", room_id=self.state.rooms["splitbrain-ops"].room_id, connection=False
        )
        holders = sorted(
            str(holder.get("name") if isinstance(holder, dict) else holder)
            for role in detail.get("roles", [])
            if role.get("name") == "arbiter"
            for holder in role.get("held_by") or []
        )
        try:
            async with self.observer.connect_in(self.room_id) as joined:
                records, _ = await read_decision_records(
                    self.observer, self.room_id, self.candidate_id, joined
                )
                _, journal = await read_correction_journal(
                    self.observer, self.room_id, self.candidate_id, joined
                )
        except ValueError as exc:
            raise SplitbrainError(
                f"Recovery expected valid snapshots for {self.candidate_id}; observed {exc}"
            ) from exc
        selected = latest_record(records)
        record = selected.state if selected else None
        context = await self.observer.op(
            "read_context", room_id=self.room_id, limit=200, connection=False
        )
        messages = context_messages(context)
        proposals = [
            message_id(item)
            for item in messages
            if item.get("sender_name") in {PRIMARY, STANDBY}
            and str(item.get("body", "")).startswith("Proposal v")
        ]
        decisions = [
            item
            for item in messages
            if item.get("sender_name") in {PRIMARY, STANDBY}
            and str(item.get("body", "")).startswith("Decision recorded:")
        ]
        proposal_text = (
            record.machine.proposals[-1].text if record and record.machine.proposals else ""
        )
        confirmations = [
            message_id(item)
            for item in messages
            if item.get("sender_name") == self.decision.confirm["as"]
            and item.get("body") == self.decision.confirm["text"]
        ]
        corrections = []
        for origin in record.origins if record else []:
            context = await self.observer.op(
                "read_context", room_id=origin.room_id, limit=200, connection=False
            )
            corrections.append(
                [
                    message_id(reply)
                    for thread in context.get("threads", [])
                    if message_id(thread.get("root") or {}) == origin.thread_id
                    for reply in thread.get("replies") or []
                    if reply.get("sender_name") == SENTINEL
                    and str(reply.get("body", "")).startswith("Update:")
                    and f"#{self.room_name}." in str(reply.get("body", ""))
                    and f"Decision: {quoted_sentence(proposal_text)}" in str(reply.get("body", ""))
                ]
            )
        return RecoveryObservation(
            rooms=rooms,
            holders=holders,
            documents=sorted(item.document_id for item in records),
            proposals=proposals,
            decisions=[message_id(item) for item in decisions],
            decision_senders=[str(item["sender_name"]) for item in decisions],
            decision_matches_proposal=all(
                str(item.get("body", "")).startswith(f'Decision recorded: "{proposal_text}" ')
                for item in decisions
            ),
            confirmations=confirmations,
            corrections=corrections,
            record=record,
            journal=journal,
        )

    async def before_confirm(self, room_name: str) -> None:
        self.room_name = room_name
        self.candidate_id = "-".join(room_name.split("-")[1:3])
        rooms = await self.observer.op("list_all_rooms", connection=False)
        entries = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
        matches = [str(item["room_id"]) for item in entries if item.get("name") == room_name]
        require_equal("one conflict room before takeover", 1, len(matches))
        self.room_id = matches[0]
        self.proposed = await wait_for_observation(
            self.group,
            "the primary's persisted proposal v1 and its announcement",
            self.observe,
            lambda item: bool(
                item.record
                and item.record.machine.version == 1
                and any(
                    ident in item.record.machine.proposals[0].thread_ids for ident in item.proposals
                )
            ),
        )
        before = self.proposed
        require_equal("the primary to hold the lease", [PRIMARY], before.holders)
        require_equal("one room", [self.room_id], before.rooms)
        require_equal("one original decision document", 1, len(before.documents))
        require_equal("one proposal announcement", 1, len(before.proposals))
        self._require_open_proposal(before)
        await self.group.stop_child("arbiter")

        def adopted(item: RecoveryObservation) -> bool:
            return item.holders == [STANDBY] and any(
                f"Reused #{room_name}:" in line for line in self.group.child("arbiter-b").recent
            )

        after = await wait_for_observation(
            self.group,
            "arbiter-b to hold the exclusive lease and adopt the open room",
            self.observe,
            adopted,
        )
        self._require_open_proposal(after)
        require_equal("the same room after takeover", before.rooms, after.rooms)
        require_equal("the same documents before confirmation", before.documents, after.documents)
        require_equal("the same proposal announcement", before.proposals, after.proposals)
        require_equal("the restored proposal", before.record.machine, after.record.machine)
        print(
            f"[recovery] arbiter-b adopted #{room_name}: v1 by @{self.decision.propose['as']}, "
            "0 confirmations; sending the confirmation now.",
            flush=True,
        )

    def _require_open_proposal(self, observed: RecoveryObservation) -> None:
        record = observed.record
        if record is None:
            raise SplitbrainError("Recovery expected a versioned room document; observed none")
        require_equal("an open proposal", DecisionState.PROPOSED, record.machine.state)
        require_equal("proposal v1", 1, record.machine.version)
        require_equal(
            "the original author", self.decision.propose["as"], record.machine.proposals[0].author
        )
        require_equal("no confirmations before takeover", [], record.machine.confirmations)
        require_equal("no confirmation messages before takeover", [], observed.confirmations)
        require_equal("no decision before confirmation", [], observed.decisions)

    async def after_confirm(self, room_name: str) -> None:
        require_equal("the same conflict callback", self.room_name, room_name)
        sentinel = self.group.child("sentinel")

        async def exited() -> int | None:
            return sentinel.proc.returncode

        code = await wait_for_observation(
            self.group,
            f"the Sentinel to exit with demo code {demo_faults.EXIT_CODE}",
            exited,
            lambda value: value is not None,
        )
        require_equal("the injected Sentinel exit code", demo_faults.EXIT_CODE, code)
        crashed = await self.observe()
        if crashed.journal is None:
            raise SplitbrainError(
                "Recovery expected a correction journal after the crash; observed none"
            )
        statuses = [item.status for item in crashed.journal.threads]
        require_equal("one saved receipt and one pending thread", ["posted", "pending"], statuses)
        require_equal(
            "one observable correction before restart",
            [1, 0],
            [len(items) for items in crashed.corrections],
        )
        env = self.env.copy()
        env.pop(demo_faults.ENV_VAR, None)
        await self.group.restart_child("sentinel", self.root, env)
        completed = await wait_for_observation(
            self.group,
            "the restarted Sentinel to finish only the pending correction",
            self.observe,
            lambda item: bool(
                item.journal
                and item.journal.complete
                and item.journal.notified
                and item.record
                and item.record.corrected
            ),
        )
        self._require_complete(completed)
        require_equal(
            "the first correction receipt to survive restart",
            crashed.corrections[0],
            completed.corrections[0],
        )
        await self._repeat_confirmation()
        repeated = await wait_for_observation(
            self.group,
            "the repeated confirmation to arrive in Switch",
            self.observe,
            lambda item: len(item.confirmations) == 2,
        )
        deadline = time.monotonic() + DUPLICATE_SETTLE_S
        while True:
            self.group.check()
            repeated = await self.observe()
            self._require_complete(repeated)
            require_equal("two identical confirmation messages", 2, len(repeated.confirmations))
            require_equal(
                "unchanged decision IDs after the duplicate",
                completed.decisions,
                repeated.decisions,
            )
            require_equal(
                "unchanged correction IDs after the duplicate",
                completed.corrections,
                repeated.corrections,
            )
            require_equal(
                "unchanged documents after the duplicate", completed.documents, repeated.documents
            )
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(POLL_S)
        self.report = RecoveryReport(
            room_name=room_name,
            room_id=self.room_id,
            canonical_document_id=self.proposed.documents[0],
            recovery_document_ids=sorted(set(repeated.documents) - set(self.proposed.documents)),
            adopted_author=self.decision.propose["as"],
            decision_sender=repeated.decision_senders[0],
            sentinel_exit_code=code,
            checkpoint_statuses=statuses,
            decision_count=len(repeated.decisions),
            correction_counts=[len(items) for items in repeated.corrections],
            room_count=len(repeated.rooms),
            repeated_confirmations=len(repeated.confirmations),
        )

    def _require_complete(self, observed: RecoveryObservation) -> None:
        require_equal("one room after recovery", [self.room_id], observed.rooms)
        require_equal("one unchanged proposal", self.proposed.proposals, observed.proposals)
        require_equal("one final decision", 1, len(observed.decisions))
        require_equal("arbiter-b to record the decision", [STANDBY], observed.decision_senders)
        require_equal(
            "the announcement to preserve the agreed text", True, observed.decision_matches_proposal
        )
        require_equal(
            "one correction per original thread",
            [1, 1],
            [len(items) for items in observed.corrections],
        )
        require_equal(
            "the canonical decision document to remain",
            True,
            self.proposed.documents[0] in observed.documents,
        )
        require_equal("one standby-owned recovery snapshot", 2, len(observed.documents))
        require_equal("the final state", DecisionState.DECIDED, observed.record.machine.state)
        require_equal(
            "the same case in the takeover snapshot",
            self.candidate_id,
            observed.record.candidate.id,
        )
        require_equal("the takeover snapshot writer", STANDBY, observed.record.writer)
        require_equal("no proposal v2 in the snapshot", 1, observed.record.machine.version)
        require_equal(
            "the original proposal history",
            self.proposed.record.machine.proposals,
            observed.record.machine.proposals,
        )
        require_equal(
            "one confirmation of v1",
            [1],
            [item.version for item in observed.record.machine.confirmations],
        )

    async def _repeat_confirmation(self) -> None:
        if self.state.mattermost is None:
            raise SplitbrainError("Recovery expected Mattermost credentials")
        user = await MattermostUser.login(
            self.settings.mattermost_url,
            self.decision.confirm["as"],
            self.state.mattermost.password,
            self.settings.values.get("MATTERMOST_TEAM_NAME", "switch"),
        )
        try:
            channel = await seed._channel(user, self.room_name)
            await user.post(channel, self.decision.confirm["text"])
        finally:
            await user.aclose()
