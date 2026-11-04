"""Reproducible probe for the Switch 0.31.0 exclusive-role lease race (M7).

Run against a bootstrapped stack:

    uv run python scripts/probe_arbiter_lease.py

Two live agent streams call `assume_role("arbiter")` concurrently. The script
prints the exact result of each call, `get_room_detail(ops).roles[arbiter].held_by`
before/after, and what `release_role()` by the loser does. It leaves the role
unheld so the next demo/bootstrap run starts clean. Results are recorded in
docs/SWITCH_NOTES.md under "Verified in M7".
"""

from __future__ import annotations

import asyncio
from typing import Any

from splitbrain import bootstrap
from splitbrain.config import Settings
from splitbrain.switch.client import SwitchAgent, SwitchOpError
from splitbrain.switch.events import ConnectionStateFrame, SwitchFrame

ROLE = "arbiter"


def _agent(settings: Settings, state: bootstrap.BootstrapState, name: str) -> SwitchAgent:
    creds = state.agents[name]
    return SwitchAgent(settings.api_base_url, creds.agent_id, creds.api_key)


async def _with_stream(agent: SwitchAgent, ops_id: str) -> tuple[asyncio.Task[None], asyncio.Event]:
    ready = asyncio.Event()
    stop = asyncio.Event()

    async def handler(frame: SwitchFrame) -> None:
        if isinstance(frame, ConnectionStateFrame):
            ready.set()

    task = asyncio.create_task(agent.run(handler, stop=stop))
    await asyncio.wait_for(ready.wait(), timeout=20.0)
    await agent.op("connect_to_room", room_id=ops_id)
    return task, stop


async def _holders(observer: SwitchAgent, ops_id: str) -> list[str]:
    detail = await observer.op("get_room_detail", room_id=ops_id, connection=False)
    for role in detail.get("roles", []):
        if role.get("name") == ROLE:
            return [
                str(holder.get("name") if isinstance(holder, dict) else holder)
                for holder in role.get("held_by") or []
            ]
    return []


async def _assume(agent: SwitchAgent, label: str) -> tuple[str, str, Any]:
    try:
        result = await agent.op("assume_role", role=ROLE)
        return label, "HTTP 200", result
    except SwitchOpError as exc:
        return label, f"HTTP {exc.status}", exc.body


async def _release(agent: SwitchAgent, label: str) -> tuple[str, str, Any]:
    try:
        result = await agent.op("release_role")
        return label, "HTTP 200", result
    except SwitchOpError as exc:
        return label, f"HTTP {exc.status}", exc.body


async def main() -> None:
    settings = Settings.load()
    state = bootstrap.load_state(settings)
    ops_id = state.rooms["splitbrain-ops"].room_id
    observer = _agent(settings, state, "splitbrain-sentinel")
    primary = _agent(settings, state, "splitbrain-arbiter")
    standby = _agent(settings, state, "splitbrain-arbiter-b")
    streams: list[tuple[asyncio.Task[None], asyncio.Event]] = []
    try:
        print(f"probe: ops room {ops_id}", flush=True)
        print(f"held_by BEFORE: {await _holders(observer, ops_id)}", flush=True)
        for agent in (primary, standby):
            streams.append(await _with_stream(agent, ops_id))

        results = await asyncio.gather(
            _assume(primary, "splitbrain-arbiter"),
            _assume(standby, "splitbrain-arbiter-b"),
        )
        for label, status, body in results:
            print(f"assume_role({ROLE!r}) {label}: {status} -> {body}", flush=True)
        after = await _holders(observer, ops_id)
        print(f"held_by AFTER simultaneous assume: {after}", flush=True)
        if len(after) > 1:
            print("RESULT: exclusive lease granted to TWO agents (server race).", flush=True)
            label, status, body = await _release(standby, "splitbrain-arbiter-b")
            print(f"release_role() {label}: {status} -> {body}", flush=True)
            print(f"held_by AFTER loser released: {await _holders(observer, ops_id)}", flush=True)
        else:
            print("RESULT: only one holder; no race reproduced this time.", flush=True)

        # Leave the stack clean for the next run.
        for agent, label in ((primary, "splitbrain-arbiter"), (standby, "splitbrain-arbiter-b")):
            current = await _holders(observer, ops_id)
            if label in current:
                released = await _release(agent, label)
                print(f"cleanup {released[0]}: {released[1]} -> {released[2]}", flush=True)
        print(f"held_by AFTER cleanup: {await _holders(observer, ops_id)}", flush=True)
    finally:
        for task, stop in streams:
            stop.set()
            task.cancel()
        await asyncio.gather(*(task for task, _ in streams), return_exceptions=True)
        for agent in (primary, standby, observer):
            await agent.aclose()


if __name__ == "__main__":
    asyncio.run(main())
