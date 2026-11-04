"""M6 integration: the full detect -> verify -> convene -> decide -> correct loop.

Needs the running stack (`uv run splitbrain up && uv run splitbrain bootstrap`).
All three agents run in-process with replay cassettes and fixture evidence, so
the test needs no API key and no internet.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest

from splitbrain import bootstrap, seed
from splitbrain.agents import arbiter as arbiter_agent
from splitbrain.agents import sentinel as sentinel_agent
from splitbrain.agents import verifier as verifier_agent
from splitbrain.config import Settings
from splitbrain.switch.client import SwitchAgent
from splitbrain.switch.events import ConnectionStateFrame, SwitchFrame
from splitbrain.switch.mattermost import MattermostUser

pytestmark = pytest.mark.integration

ENGINEERING_QUOTE = "we're pulling SSO out of Q4. The auth migration has to land first."
MILESTONE_MOVE = "moved from Q4 2026 to Q1 2027 on Nov 4"


async def _until(predicate: Any, timeout: float, description: str) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Timed out waiting for {description}")
        await asyncio.sleep(0.2)


async def _read_room_context(settings: Settings, state: bootstrap.BootstrapState) -> Any:
    """A short-lived stream is required by connect_to_room / load_internal_documents."""
    creds = state.agents["splitbrain-sentinel"]
    agent = SwitchAgent(settings.api_base_url, creds.agent_id, creds.api_key)
    ready = asyncio.Event()
    stop = asyncio.Event()

    async def handler(frame: SwitchFrame) -> None:
        if isinstance(frame, ConnectionStateFrame):
            ready.set()

    task = asyncio.create_task(agent.run(handler, stop=stop))
    await asyncio.wait_for(ready.wait(), timeout=20)
    return agent, task, stop


async def test_full_sso_cycle_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_LLM_MODE", "replay")
    monkeypatch.setenv("SPLITBRAIN_EVIDENCE_MODE", "fixture")
    monkeypatch.setenv("SPLITBRAIN_CONSENT_TIMEOUT_S", "120")
    monkeypatch.setenv("SPLITBRAIN_EVIDENCE_TIMEOUT_S", "60")

    settings = Settings.load()
    state = bootstrap.load_state(settings)
    assert state.mattermost is not None
    # An isolated store: a previous demo run would otherwise leave active claims
    # that match this run's messages and create a second, stale candidate.
    monkeypatch.setattr(sentinel_agent, "DB_FILENAME", f"sentinel-it-{uuid.uuid4().hex[:8]}.db")

    stop = asyncio.Event()
    runtimes = [
        sentinel_agent.build_runtime(settings, stop=stop),
        arbiter_agent.build_runtime(settings, stop=stop),
        verifier_agent.build_runtime(settings, stop=stop),
    ]
    sentinel_proc, arbiter_proc, verifier_proc = (rt.processor for rt in runtimes)
    tasks = [asyncio.create_task(rt.serve(), name=f"it-{i}") for i, rt in enumerate(runtimes)]
    try:
        await _until(
            lambda: (
                arbiter_proc.is_holder
                and verifier_proc.provider is not None
                and len(sentinel_proc.claimed) >= 5
            ),
            30.0,
            "all three agent streams to attach, claim rooms and take their roles",
        )
        result = await seed.run(settings, "sso", auto_decide=True)
    finally:
        stop.set()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=20.0)

    assert result.conflict_room_name and result.conflict_room_name.startswith("conflict-")
    password = state.mattermost.password
    team = settings.values.get("MATTERMOST_TEAM_NAME", "switch")
    maria = await MattermostUser.login(settings.mattermost_url, "maria", password, team)
    tomas = await MattermostUser.login(settings.mattermost_url, "tomas", password, team)
    try:
        sales = [p for p in result.posted if p.message.room == "sales"]
        engineering = [p for p in result.posted if p.message.room == "engineering"]
        assert len(sales) == 1 and len(engineering) == 1

        sales_thread = await maria.thread(sales[0].post_id)
        assert any(
            "Update: @maria and @tomas resolved a conflict about SSO for Acme" in post.message
            for post in sales_thread
        ), "the sales correction is not a reply in the original thread"

        engineering_thread = await tomas.thread(engineering[0].post_id)
        assert any(
            "May I quote it in a private resolution room" in post.message
            for post in engineering_thread
        ), "the consent question is missing from tomas's thread"
        assert any(post.message.strip() == "yes" for post in engineering_thread), "missing 'yes'"
        assert any(
            "Update: @maria and @tomas resolved a conflict about SSO for Acme" in post.message
            for post in engineering_thread
        ), "the engineering correction is not a reply in the original thread"
    finally:
        await maria.aclose()
        await tomas.aclose()

    # Read Switch artifacts with a short-lived stream, after the agents stopped.
    agent, task, stream_stop = await _read_room_context(settings, state)
    try:
        ops_id = state.rooms["splitbrain-ops"].room_id
        context = await agent.op("read_context", room_id=ops_id, limit=120, connection=False)
        bodies = [
            entry["body"]
            for thread in context["threads"]
            for entry in [thread["root"], *thread["replies"]]
        ]
        assert any("sb:candidate " in body for body in bodies)
        assert all(ENGINEERING_QUOTE not in body for body in bodies if "sb:candidate" in body)
        assert any(MILESTONE_MOVE in body and "sb:evidence " in body for body in bodies)
        assert any("sb:verdict " in body and "confirmed" in body for body in bodies)
        assert any("sb:consent " in body and '"granted":true' in body for body in bodies)
        assert any("sb:decided " in body for body in bodies)
        assert any("sb:corrected " in body for body in bodies)

        rooms = await agent.op("list_all_rooms", connection=False)
        entries = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
        conflict = next((r for r in entries if r.get("name") == result.conflict_room_name), None)
        assert conflict is not None
        room_id = str(conflict["room_id"])
        detail = await agent.op("get_room_detail", room_id=room_id, connection=False)
        assert {"maria", "tomas"} <= set(detail.get("connected_user_names") or [])

        joined = await agent.op("connect_to_room", room_id=room_id)
        labels = {link["label"] for link in joined.get("linked_rooms", [])}
        assert "origin: #sales (maria)" in labels
        assert "origin: #engineering (tomas)" in labels
        document_ids = [str(d["id"]) for d in joined.get("documents", []) if d.get("id")]
        documents = await agent.op("load_internal_documents", ids=document_ids)
        record = "\n".join(str(item.get("content", "")) for item in documents)
        assert "Status: DECIDED" in record
        assert MILESTONE_MOVE in record
        assert "Corrections posted in #sales, #engineering" in record
        assert 'Decision: "SSO beta for Acme on December 15, GA in Q1.' in record

        timeline = await agent.op("read_context", room_id=room_id, limit=60, connection=False)
        posts = [
            entry["body"]
            for thread in timeline["threads"]
            for entry in [thread["root"], *thread["replies"]]
        ]
        assert any("Splitbrain found two statements" in body for body in posts)
        assert any(ENGINEERING_QUOTE in body for body in posts), "the granted quote is missing"
        assert any("decision: SSO beta for Acme" in body for body in posts)
        assert any(body.strip() == "confirm" for body in posts)
        assert any("Recorded. Correcting the original threads now." in body for body in posts)
        assert any("Corrections posted" in body for body in posts)
    finally:
        stream_stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await agent.aclose()
