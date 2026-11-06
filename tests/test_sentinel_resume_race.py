"""Coverage readiness and the observed first-document-read failure, without Switch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from decision_fakes import FakeSwitch
from test_decision_integrity import decided_arbiter, decision_frame, sentinel_for

from splitbrain.core.decision_record import (
    CorrectionJournal,
    load_correction_journal,
    load_decision_records,
    pending_corrections,
)
from splitbrain.core.protocol import DecidedPacket
from splitbrain.switch.client import SwitchAgent, SwitchOpError
from splitbrain.switch.events import MessageFrame

ROOM = "r-conflict"
MISSING_CONTEXT = "Not connected to a room. Call connect_to_room first."


@pytest.fixture
async def journal() -> CorrectionJournal:
    _, _, _, packet = await decided_arbiter()
    progress = pending_corrections(packet.origins)
    progress[0].status = "posted"
    progress[0].message_id = "sw-first-correction"
    return CorrectionJournal(decided=packet, threads=progress)


class SlowClaimAgent(FakeSwitch):
    def __init__(self) -> None:
        super().__init__("splitbrain-sentinel")
        self.claim_entered = asyncio.Event()
        self.finish_claim = asyncio.Event()

    @asynccontextmanager
    async def act_in(self, room_id: str) -> AsyncIterator[SlowClaimAgent]:
        async with super().act_in(room_id):
            if asyncio.current_task().get_name() == "coverage-claim":
                self.claim_entered.set()
                await self.finish_claim.wait()
            yield self


async def test_resume_waits_for_a_concurrent_claim_before_loading_the_journal(
    journal: CorrectionJournal, tmp_path: Path, llm_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = SlowClaimAgent()
    agent.state.documents["doc-journal"] = {
        "id": "doc-journal",
        "room_id": ROOM,
        "owner": "splitbrain-sentinel",
        "name": "SB-0001 correction progress",
        "content": journal.render(),
    }
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    entered_resume = asyncio.Event()
    loaded: list[CorrectionJournal] = []

    async def resume(frame: MessageFrame, packet: DecidedPacket) -> None:
        entered_resume.set()
        assert ROOM in sentinel.claimed
        _, saved = await load_correction_journal(agent, ROOM, packet.candidate_id)
        loaded.append(saved)

    monkeypatch.setattr(sentinel, "_resume_corrections", resume)
    claim = asyncio.create_task(sentinel._claim_room(ROOM), name="coverage-claim")
    await asyncio.wait_for(agent.claim_entered.wait(), timeout=1)
    resumed = asyncio.create_task(
        sentinel._apply_corrections(decision_frame(journal.decided), journal.decided)
    )
    try:
        await asyncio.sleep(0)
        assert not entered_resume.is_set(), "resume started while the room claim was still pending"
        assert ROOM not in sentinel.claimed, "a pending claim was advertised as completed"
    finally:
        agent.finish_claim.set()
        results = await asyncio.gather(claim, resumed, return_exceptions=True)
        await sentinel.aclose()
    assert results == [None, None]
    assert loaded == [journal]


async def test_a_failed_claim_remains_retryable_before_resuming_corrections(
    journal: CorrectionJournal, tmp_path: Path, llm_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = FakeSwitch("splitbrain-sentinel")
    original_op = agent.op
    failed = False

    async def op(name: str, /, **args: Any) -> Any:
        nonlocal failed
        if name == "connect_to_room" and not failed:
            failed = True
            raise SwitchOpError(name, 503, "temporarily unavailable")
        return await original_op(name, **args)

    monkeypatch.setattr(agent, "op", op)
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    resume = AsyncMock()
    monkeypatch.setattr(sentinel, "_resume_corrections", resume)
    try:
        await sentinel._claim_room(ROOM)
        assert ROOM not in sentinel.claimed
        resume.assert_not_awaited()
        await sentinel._apply_corrections(decision_frame(journal.decided), journal.decided)
        assert ROOM in sentinel.claimed
        resume.assert_awaited_once()
    finally:
        await sentinel.aclose()


class DocumentServer:
    def __init__(self, journal: CorrectionJournal) -> None:
        self.content = journal.render()
        self.name = "SB-0001 correction progress"
        self.errors: list[tuple[int, Any]] = [(400, {"detail": MISSING_CONTEXT})]
        self.calls: list[str] = []
        self.connection_ids: set[str] = set()
        self.document_read = asyncio.Event()
        self.claim_attempted = asyncio.Event()
        self.wait_for_claim = False

    async def handle(self, request: httpx.Request) -> httpx.Response:
        operation = request.url.path.rsplit("/", 1)[-1]
        self.calls.append(operation)
        self.connection_ids.add(request.headers["X-Switch-Connection-Id"])
        if operation == "connect_to_room":
            return httpx.Response(
                200, json={"result": {"documents": [{"id": "doc-journal", "name": self.name}]}}
            )
        assert operation == "load_internal_documents"
        assert json.loads(request.content) == {"ids": ["doc-journal"]}
        self.document_read.set()
        if self.wait_for_claim:
            await self.claim_attempted.wait()
        if self.errors:
            status, body = self.errors.pop(0)
            return httpx.Response(status, json=body)
        return httpx.Response(
            200, json={"result": [{"id": "doc-journal", "content": self.content}]}
        )


async def test_journal_context_loss_during_a_concurrent_claim_reconnects_once(
    journal: CorrectionJournal, tmp_path: Path, llm_factory: Any, caplog: pytest.LogCaptureFixture
) -> None:
    server = DocumentServer(journal)
    server.wait_for_claim = True
    async with httpx.AsyncClient(transport=httpx.MockTransport(server.handle)) as client:
        agent = SwitchAgent(
            "http://switch.test",
            "sentinel",
            "unit-test-key",
            connection_id="race-connection",
            client=client,
        )
        sentinel = sentinel_for(agent, llm_factory, tmp_path)

        async def claim() -> None:
            await server.document_read.wait()
            server.claim_attempted.set()
            await sentinel._claim_room(ROOM)

        try:
            result, _ = await asyncio.wait_for(
                asyncio.gather(
                    load_correction_journal(agent, ROOM, journal.decided.candidate_id), claim()
                ),
                timeout=2,
            )
            assert result == ("doc-journal", journal)
            assert ROOM in sentinel.claimed
            assert server.calls == [
                "connect_to_room",
                "connect_to_room",
                "load_internal_documents",
                "connect_to_room",
                "load_internal_documents",
                "connect_to_room",
            ]
            assert server.connection_ids == {"race-connection"}
            assert sum("retrying once" in record.message for record in caplog.records) == 1
        finally:
            await sentinel.aclose()


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (400, {"detail": "Unknown document"}),
        (400, {"detail": "Not connected to a room you can access"}),
        (403, {"detail": MISSING_CONTEXT}),
        (500, {"detail": MISSING_CONTEXT}),
        (400, "Not connected to a room"),
    ],
)
async def test_other_document_errors_are_not_retried(
    status: int, body: Any, journal: CorrectionJournal, caplog: pytest.LogCaptureFixture
) -> None:
    server = DocumentServer(journal)
    server.errors = [(status, body)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(server.handle)) as client:
        agent = SwitchAgent("http://switch.test", "sentinel", "unit-test-key", client=client)
        with pytest.raises(SwitchOpError) as error:
            await load_correction_journal(agent, ROOM, journal.decided.candidate_id)
        assert error.value.status == status
        assert server.calls.count("load_internal_documents") == 1
        assert not caplog.records


async def test_missing_context_is_retried_only_once(
    journal: CorrectionJournal, caplog: pytest.LogCaptureFixture
) -> None:
    server = DocumentServer(journal)
    server.errors *= 2
    async with httpx.AsyncClient(transport=httpx.MockTransport(server.handle)) as client:
        agent = SwitchAgent("http://switch.test", "sentinel", "unit-test-key", client=client)
        with pytest.raises(SwitchOpError, match="Not connected to a room"):
            await load_correction_journal(agent, ROOM, journal.decided.candidate_id)
        assert server.calls.count("load_internal_documents") == 2
        assert server.calls.count("connect_to_room") == 3
        assert sum("retrying once" in record.message for record in caplog.records) == 1


async def test_decision_record_read_uses_the_same_bounded_context_recovery(
    journal: CorrectionJournal,
) -> None:
    server = DocumentServer(journal)
    server.name = "SB-0001 decision record"
    server.content = "Status: DECIDED"
    async with httpx.AsyncClient(transport=httpx.MockTransport(server.handle)) as client:
        agent = SwitchAgent("http://switch.test", "sentinel", "unit-test-key", client=client)
        records, _ = await load_decision_records(agent, ROOM, journal.decided.candidate_id)
        assert records[0].content == "Status: DECIDED"
        assert server.calls.count("load_internal_documents") == 2
