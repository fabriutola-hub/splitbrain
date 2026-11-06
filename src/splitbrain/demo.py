"""`splitbrain demo` and `run all` — one command, clean state, honest banners.

The parent owns the Docker stack, bootstrap, four child agent processes and the
seed script. Children are started in their own process group so Ctrl+C reaches
only the parent, which then terminates them cleanly. Every degraded mode is
announced before anything happens and repeated in the final summary.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import httpx

from . import bootstrap, demo_faults, seed, stack
from .agents import sentinel as sentinel_agent
from .config import (
    LLMSettings,
    Paths,
    Settings,
    SplitbrainError,
    ensure_env,
    loopback_client,
)
from .core.packets import decode
from .evidence.github import FIXTURE_BANNER
from .evidence.scenario import ENV_VAR as SCENARIO_EVIDENCE_ENV
from .evidence.scenario import load_entry
from .recovery_demo import RecoveryDemo, RecoveryReport
from .switch.client import SwitchAgent

AGENT_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sentinel", ("run", "sentinel")),
    ("arbiter", ("run", "arbiter")),
    ("verifier", ("run", "verifier")),
    # The standby is deliberately last: see _primary_lease_confirmed below.
    ("arbiter-b", ("run", "arbiter-b")),
)
COLORS = {"sentinel": "36", "arbiter": "35", "arbiter-b": "34", "verifier": "33"}
RESET = "\x1b[0m"
AGENTS_READY_TIMEOUT_S = 60.0
CONFLICT_TIMEOUT_S = 180.0
HUMAN_CONFLICT_TIMEOUT_S = 900.0  # a person may need to answer consent first
BRIEF_TIMEOUT_S = 90.0
HUMAN_DECISION_TIMEOUT_S = 900.0
PACKET_TIMEOUT_S = 30.0
POLL_S = 0.5


def _color(name: str) -> str:
    if os.environ.get("NO_COLOR"):
        return ""
    return f"\x1b[{COLORS[name]}m"


@dataclass(frozen=True, slots=True)
class DemoModes:
    llm_mode: str
    llm_model: str
    llm_base_url: str
    evidence_mode: str
    repo: str
    scenario_evidence: str | None
    degraded: tuple[str, ...]
    clean_state: str

    def print_banners(self) -> None:
        for line in self.degraded:
            print(line, flush=True)
        if self.llm_mode == "live":
            print(f"LLM: live | model={self.llm_model} | base_url={self.llm_base_url}", flush=True)
        if self.evidence_mode == "live":
            print(f"EVIDENCE: live (GitHub REST, {self.repo})", flush=True)


def resolve_modes(*, offline: bool, scenario: str, paths: Paths) -> DemoModes:
    # mode="replay" never validates the key, so this probe works with or without
    # .env.local and without honouring a stale SPLITBRAIN_LLM_MODE from the shell.
    probe = LLMSettings.load(mode="replay")
    has_key = bool(probe.api_key)
    explicit_mode = os.environ.get("SPLITBRAIN_LLM_MODE", "").strip().lower()
    if offline or not has_key:
        llm_mode = "replay"
    elif explicit_mode in ("live", "record"):
        llm_mode = explicit_mode
    else:
        llm_mode = "live"
    evidence_mode = "fixture" if offline else "live"
    scenario_evidence = "hackathon" if scenario == "hackathon" else None

    degraded: list[str] = []
    if llm_mode == "replay":
        reason = "no SPLITBRAIN_LLM_API_KEY" if not has_key else "forced by --offline"
        degraded.append(
            f"[DEGRADED] LLM replay ({reason}): recorded cassettes only, no model calls."
        )
    if evidence_mode == "fixture":
        degraded.append(FIXTURE_BANNER)
    if scenario_evidence:
        degraded.append(load_entry(scenario_evidence, paths).banner())
    return DemoModes(
        llm_mode=llm_mode,
        llm_model=probe.model,
        llm_base_url=probe.base_url,
        evidence_mode=evidence_mode,
        repo=bootstrap.roadmap_repo(Settings.load(require_env_file=False)),
        scenario_evidence=scenario_evidence,
        degraded=tuple(degraded),
        clean_state="",
    )


def child_environment(modes: DemoModes) -> dict[str, str]:
    env = os.environ.copy()
    env["SPLITBRAIN_LLM_MODE"] = modes.llm_mode
    env["SPLITBRAIN_EVIDENCE_MODE"] = modes.evidence_mode
    if modes.scenario_evidence:
        env[SCENARIO_EVIDENCE_ENV] = modes.scenario_evidence
    else:
        env.pop(SCENARIO_EVIDENCE_ENV, None)
    return env


@dataclass(slots=True)
class Child:
    name: str
    proc: asyncio.subprocess.Process
    recent: list[str] = field(default_factory=list)
    reader: asyncio.Task[None] | None = None
    expected_stop: bool = False
    expected_returncode: int | None = None


class AgentGroup:
    def __init__(self, children: list[Child]) -> None:
        self.children = children
        self.stopped = False

    def check(self) -> None:
        for child in self.children:
            if child.proc.returncode is not None:
                if child.expected_stop or child.proc.returncode == child.expected_returncode:
                    continue
                tail = " | ".join(child.recent[-6:])
                raise SplitbrainError(
                    f"Agent {child.name!r} exited early with code {child.proc.returncode}. "
                    f"Last lines: {tail or '(no output)'}"
                )

    def child(self, name: str) -> Child:
        for child in self.children:
            if child.name == name:
                return child
        raise SplitbrainError(f"Recovery expected an agent process named {name!r}")

    async def stop_child(self, name: str) -> None:
        child = self.child(name)
        self.check()
        child.expected_stop = True
        child.proc.terminate()
        try:
            await asyncio.wait_for(child.proc.wait(), timeout=8.0)
        except TimeoutError:
            child.proc.kill()
            await child.proc.wait()
        print(f"[recovery] stopped {name} (pid {child.proc.pid}).", flush=True)

    async def restart_child(self, name: str, root: Path, env: dict[str, str]) -> Child:
        previous = self.child(name)
        if previous.proc.returncode is None:
            raise SplitbrainError(f"Recovery expected {name!r} to exit before restart")
        if previous.reader is not None:
            await asyncio.wait_for(previous.reader, timeout=5.0)
        argv = dict(AGENT_COMMANDS)[name]
        child = await _start_child(root, env, name, argv)
        self.children[self.children.index(previous)] = child
        return child

    async def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        live = [child.proc for child in self.children if child.proc.returncode is None]
        for proc in live:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        if live:
            try:
                await asyncio.wait_for(asyncio.gather(*(proc.wait() for proc in live)), timeout=8.0)
            except TimeoutError:
                for proc in live:
                    if proc.returncode is None:
                        proc.kill()
                await asyncio.gather(*(proc.wait() for proc in live), return_exceptions=True)
        readers = [child.reader for child in self.children if child.reader is not None]
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        print("[demo] agents stopped.", flush=True)


async def _pump(child: Child) -> None:
    assert child.proc.stdout is not None
    paint = _color(child.name)
    prefix = f"{paint}[{child.name:<11}]{RESET} " if paint else f"[{child.name:<11}] "
    while True:
        line = await child.proc.stdout.readline()
        if not line:
            return
        text = line.decode("utf-8", errors="replace").rstrip()
        child.recent.append(text)
        del child.recent[:-20]
        print(f"{prefix}{text}", flush=True)


async def _primary_lease_confirmed(
    settings: Settings, state: bootstrap.BootstrapState, timeout_s: float = 30.0
) -> bool:
    """Wait until splitbrain-arbiter holds the role (not just any Arbiter)."""
    creds = state.agents.get("splitbrain-sentinel")
    ops = state.rooms.get("splitbrain-ops")
    if creds is None or ops is None:
        return False
    observer = SwitchAgent(settings.api_base_url, creds.agent_id, creds.api_key)
    try:
        deadline = time.monotonic() + timeout_s
        while True:
            detail = await observer.op("get_room_detail", room_id=ops.room_id, connection=False)
            holders = [
                str(holder.get("name") if isinstance(holder, dict) else holder)
                for role in detail.get("roles", [])
                if role.get("name") == "arbiter"
                for holder in role.get("held_by") or []
            ]
            if "splitbrain-arbiter" in holders:
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.25)
    finally:
        await observer.aclose()


async def start_agents(
    root: Path, env: dict[str, str], *, settings: Settings, state: bootstrap.BootstrapState
) -> AgentGroup:
    children: list[Child] = []
    for name, argv in AGENT_COMMANDS:
        if name == "arbiter-b":
            # Switch 0.31.0 grants the exclusive lease to two agents that assume
            # it at the same instant (scripts/probe_arbiter_lease.py). Start the
            # standby only once the primary's lease is confirmed; if that cannot
            # be verified, fall back to a >= 8 s delay so it is clearly standby.
            if await _primary_lease_confirmed(settings, state):
                print(
                    "[demo] primary arbiter lease confirmed; starting standby arbiter-b.",
                    flush=True,
                )
            else:
                print(
                    "[demo] WARNING: primary arbiter lease could not be confirmed; "
                    "starting arbiter-b after an 8 s delay.",
                    flush=True,
                )
                await asyncio.sleep(8.0)
        children.append(await _start_child(root, env, name, argv))
    return AgentGroup(children)


async def _start_child(root: Path, env: dict[str, str], name: str, argv: tuple[str, ...]) -> Child:
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        import subprocess

        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    child_env = env.copy()
    if name != "sentinel":
        child_env.pop(demo_faults.ENV_VAR, None)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "splitbrain",
        *argv,
        cwd=str(root),
        env=child_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        **kwargs,
    )
    child = Child(name=name, proc=proc)
    child.reader = asyncio.create_task(_pump(child), name=f"demo-log-{name}")
    print(f"[demo] started {name} (pid {proc.pid})", flush=True)
    return child


async def _healthy(settings: Settings) -> bool:
    async with loopback_client() as client:
        try:
            response = await client.get(settings.health_url, timeout=3.0)
        except httpx.TransportError:
            return False
    return response.status_code == 200 and response.json().get("status") == "ok"


async def prepare_clean_state(*, keep: bool) -> tuple[Settings, str]:
    """Always start from a Sentinel store that matches the server's rooms."""
    initial = Settings.load(require_env_file=False)
    if ensure_env(initial.paths):
        print("[demo] created deploy/.env with fresh random secrets.", flush=True)
    settings = Settings.load()
    if keep:
        if not await _healthy(settings):
            print("[demo] --keep: stack is down, starting it.", flush=True)
            await stack.up(settings)
        db = settings.paths.state_dir / sentinel_agent.DB_FILENAME
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{db}{suffix}")
            if path.is_file():
                path.unlink()
        description = f"--keep: reused the stack, reset {db.name}"
    else:
        print(
            "[demo] clean state: down --wipe + up (volumes and .splitbrain/ removed).", flush=True
        )
        await stack.down(settings, wipe=True)
        await stack.up(settings)
        description = "down --wipe + up (fresh Switch/Mattermost databases and Sentinel store)"
    print(f"[demo] {description}", flush=True)
    return settings, description


async def _observer(settings: Settings, state: bootstrap.BootstrapState) -> SwitchAgent:
    creds = state.agents.get("splitbrain-sentinel")
    if creds is None:
        raise SplitbrainError("No Sentinel credentials; bootstrap did not finish.")
    return SwitchAgent(settings.api_base_url, creds.agent_id, creds.api_key)


async def _wait_for_agents(
    group: AgentGroup, observer: SwitchAgent, state: bootstrap.BootstrapState
) -> None:
    ops = state.rooms.get("splitbrain-ops")
    if ops is None:
        raise SplitbrainError("splitbrain-ops is missing from .splitbrain/state.json")
    deadline = time.monotonic() + AGENTS_READY_TIMEOUT_S
    while True:
        group.check()
        detail = await observer.op("get_room_detail", room_id=ops.room_id, connection=False)
        holders = [
            str(holder.get("name") if isinstance(holder, dict) else holder)
            for role in detail.get("roles", [])
            if role.get("name") == "arbiter"
            for holder in role.get("held_by") or []
        ]
        if holders:
            print(f"[demo] arbiter lease held by {', '.join(holders)}.", flush=True)
            break
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                "Timed out waiting for an Arbiter to assume the exclusive role. "
                "Check the agent logs above (ReplayMiss and HTTP errors fail loudly)."
            )
        await asyncio.sleep(POLL_S)
    # The Verifier loads the GitHub reference on its own connection_state frame.
    await asyncio.sleep(2.0)
    group.check()


async def _ops_packet(observer: SwitchAgent, ops_id: str, kind: str) -> dict[str, Any] | None:
    context = await observer.op("read_context", room_id=ops_id, limit=200, connection=False)
    bodies = [
        str(entry.get("body", ""))
        for thread in context.get("threads", [])
        for entry in [thread.get("root", {}), *(thread.get("replies") or [])]
    ]
    for body in reversed(bodies):
        for line in reversed(body.splitlines()):
            if line.strip().startswith(f"sb:{kind} "):
                decoded = decode(line.strip())
                if decoded is not None and decoded[0] == kind:
                    return decoded[1]
    return None


async def _wait_for_packet(
    group: AgentGroup, observer: SwitchAgent, ops_id: str, kind: str, timeout_s: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        group.check()
        packet = await _ops_packet(observer, ops_id, kind)
        if packet is not None:
            return packet
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                f"Timed out after {timeout_s:.0f}s waiting for an sb:{kind} packet in "
                "splitbrain-ops. See the agent logs above."
            )
        await asyncio.sleep(POLL_S)


async def _wait_for_human_close(
    group: AgentGroup,
    observer: SwitchAgent,
    ops_id: str,
    conflict_room: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Wait for the human decision's corrections and the Arbiter's closing line."""
    await _wait_for_packet(group, observer, ops_id, "corrected", HUMAN_DECISION_TIMEOUT_S)
    await _wait_for_room_marker(
        group, observer, conflict_room, seed.CORRECTIONS_MARKER, seed.CORRECTIONS_TIMEOUT_S
    )
    decided = await _ops_packet(observer, ops_id, "decided")
    corrected = await _ops_packet(observer, ops_id, "corrected")
    decision = decided.get("decision", {}) if decided else None
    corrections = list(corrected.get("rooms", [])) if corrected else []
    return decision, corrections


async def _wait_for_followup_silence(group: AgentGroup, timeout_s: float = 15.0) -> None:
    """Wait until the Sentinel has also classified Pablo's compatible follow-up message."""
    sentinel = next((child for child in group.children if child.name == "sentinel"), None)
    if sentinel is None:
        return
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        group.check()
        lines = list(sentinel.recent)
        reminder_idx = next((i for i, line in enumerate(lines) if "Reminder posted" in line), -1)
        if reminder_idx >= 0 and any("No alert:" in line for line in lines[reminder_idx + 1 :]):
            return
        await asyncio.sleep(POLL_S)


async def _wait_for_conflict(
    group: AgentGroup, observer: SwitchAgent, existing: set[str], timeout_s: float
) -> str:
    deadline = time.monotonic() + timeout_s
    while True:
        group.check()
        fresh = sorted((await seed._conflict_rooms(observer)) - existing)
        if fresh:
            return fresh[0]
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                f"Timed out after {timeout_s:.0f}s waiting for a NEW conflict-* room. "
                "Check the verdict, the evidence and the consent step in the agent logs."
            )
        await asyncio.sleep(POLL_S)


_WARNED_DUPLICATE_ROOMS: set[str] = set()


async def _conflict_room_ids(observer: SwitchAgent, room_name: str) -> list[str]:
    """Defence in depth only: Switch permits two rooms with the same name."""
    rooms = await observer.op("list_all_rooms", connection=False)
    entries = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
    ids = [str(entry["room_id"]) for entry in entries if entry.get("name") == room_name]
    if len(ids) > 1 and room_name not in _WARNED_DUPLICATE_ROOMS:
        _WARNED_DUPLICATE_ROOMS.add(room_name)
        print(
            f"[demo] WARNING: {len(ids)} Switch rooms share the name #{room_name}. "
            "This is a leftover duplicate (the Arbiter now reuses by name); "
            "reading both to find the one with the brief.",
            flush=True,
        )
    if not ids:
        raise SplitbrainError(f"Conflict room {room_name!r} is missing from the room registry")
    return ids


async def _room_bodies(observer: SwitchAgent, room_id: str, limit: int = 60) -> list[str]:
    context = await observer.op("read_context", room_id=room_id, limit=limit, connection=False)
    return [
        str(entry.get("body", ""))
        for thread in context.get("threads", [])
        for entry in [thread.get("root", {}), *(thread.get("replies") or [])]
    ]


async def _brief_in(observer: SwitchAgent, room_id: str) -> str | None:
    return next(
        (body for body in await _room_bodies(observer, room_id) if seed.BRIEF_MARKER in body),
        None,
    )


async def _wait_for_room_marker(
    group: AgentGroup,
    observer: SwitchAgent,
    room_name: str,
    marker: str,
    timeout_s: float,
) -> str:
    """Wait for a chat line that starts with `marker` in a conflict room."""
    deadline = time.monotonic() + timeout_s
    while True:
        group.check()
        for room_id in await _conflict_room_ids(observer, room_name):
            for body in await _room_bodies(observer, room_id, limit=200):
                if any(line.startswith(marker) for line in body.splitlines()):
                    return body
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                f"Timed out after {timeout_s:.0f}s waiting for the Arbiter's "
                f"{marker!r} closing line in #{room_name}. The demo summary promises "
                "that line after the Sentinel corrects both threads; check the arbiter logs."
            )
        await asyncio.sleep(POLL_S)


async def _wait_for_brief(
    group: AgentGroup, observer: SwitchAgent, room_name: str, timeout_s: float
) -> tuple[str, str]:
    deadline = time.monotonic() + timeout_s
    while True:
        group.check()
        for room_id in await _conflict_room_ids(observer, room_name):
            brief = await _brief_in(observer, room_id)
            if brief is not None:
                return room_id, brief
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                f"Timed out after {timeout_s:.0f}s waiting for the brief in {room_name!r}."
            )
        await asyncio.sleep(POLL_S)


def _room_url(settings: Settings, room: str) -> str:
    team = settings.values.get("MATTERMOST_TEAM_NAME", "switch")
    return f"{settings.mattermost_url}/{team}/channels/{room}"


def print_consent_instructions(
    scenario: seed.Scenario, state: bootstrap.BootstrapState, settings: Settings
) -> None:
    """A private quote needs the author's 'yes' BEFORE the conflict room exists."""
    private = [
        message
        for message in scenario.messages
        if (room := state.rooms.get(message.room)) is not None
        and room.channel_type == "channel_private"
    ]
    if not private:
        return
    print("\n" + "-" * 72, flush=True)
    print("A person must answer the consent question first:", flush=True)
    for message in private:
        print(
            f"  @{message.person}: reply 'yes' to Splitbrain's question in "
            f"#{message.room} at {_room_url(settings, message.room)}",
            flush=True,
        )
    print("  Without an answer the quote stays withheld after the consent timeout.", flush=True)
    print("-" * 72 + "\n", flush=True)


def print_decision_instructions(
    scenario: seed.Scenario, conflict_room: str, settings: Settings
) -> None:
    """Exactly what the two authors must write in the conflict room."""
    decision = scenario.decision
    if decision is None:
        return
    people = scenario.people
    proposer = decision.propose["as"]
    confirmer = decision.confirm["as"]
    print("\n" + "-" * 72, flush=True)
    print(f"Waiting for a HUMAN decision in #{conflict_room}.", flush=True)
    print(f"  {people.get(proposer, proposer)} (@{proposer}) writes:", flush=True)
    print("      decision: <what you agreed>", flush=True)
    print(f"  {people.get(confirmer, confirmer)} (@{confirmer}) replies:", flush=True)
    print("      confirm", flush=True)
    print(f"  Only those two can close it. {_room_url(settings, conflict_room)}", flush=True)
    print("  Press Ctrl+C to stop without deciding.", flush=True)
    print("-" * 72 + "\n", flush=True)


def print_summary(
    *,
    settings: Settings,
    state: bootstrap.BootstrapState,
    modes: DemoModes,
    scenario: str,
    conflict_room: str | None,
    decision: dict[str, Any] | None,
    corrections: list[str],
    note: str,
    followup_summary: str | None = None,
) -> None:
    print("\n" + "=" * 72, flush=True)
    print("DEMO SUMMARY", flush=True)
    print("=" * 72, flush=True)
    print(f"Scenario:      {scenario}", flush=True)
    print(f"Clean state:   {modes.clean_state}", flush=True)
    rooms = [name for name in bootstrap.STATE_ROOMS if name in state.rooms]
    if conflict_room:
        rooms.append(conflict_room)
    print(f"Rooms created: {', '.join(rooms)}", flush=True)
    parts = conflict_room.split("-") if conflict_room else []
    conflict_id = "-".join(parts[1:3]) if len(parts) >= 3 else None
    print(
        f"Conflict:      {conflict_id or 'none'}"
        + (f"  (#{conflict_room})" if conflict_room else ""),
        flush=True,
    )
    if decision:
        print(f'Decision:      "{decision.get("text", "")}"', flush=True)
        print(
            f"               proposed by @{decision.get('proposed_by', '?')}, "
            f"confirmed by @{decision.get('confirmed_by', '?')}",
            flush=True,
        )
    else:
        print("Decision:      none (scenario stops at the conflict room)", flush=True)
    print(
        "Corrections:   "
        + (", ".join(f"#{name}" for name in corrections) if corrections else "not posted yet"),
        flush=True,
    )
    if followup_summary:
        print(f"Follow-up:     {followup_summary}", flush=True)
    print(f"Note:          {note}", flush=True)
    password = state.mattermost.password if state.mattermost else "(bootstrap incomplete)"
    print("Mattermost (browser):", flush=True)
    if conflict_room:
        print(f"  conflict room  {_room_url(settings, conflict_room)}", flush=True)
    for username, channel in (("maria", "sales"), ("tomas", "engineering")):
        print(
            f"  {username:<13} login={username} / {password}   {_room_url(settings, channel)}",
            flush=True,
        )
    if scenario == "hackathon":
        for username, channel in (
            ("page-prizes", "hackathon-prizes"),
            ("page-judging", "hackathon-judging"),
        ):
            print(
                f"  {username:<13} login={username} / {password}   {_room_url(settings, channel)}",
                flush=True,
            )
    print("-" * 72, flush=True)
    for line in modes.degraded:
        print(line, flush=True)
    if not modes.degraded:
        print("No degraded modes: live LLM and live GitHub evidence.", flush=True)
    print("=" * 72, flush=True)


def validate_options(
    *, scenario: str, auto_decide: bool, followup: bool = False, recovery: bool = False
) -> None:
    for option, enabled in (("--followup", followup), ("--recovery", recovery)):
        if enabled and (scenario != "sso" or not auto_decide):
            raise SplitbrainError(f"{option} requires --scenario sso and --auto-decide.")


async def run(
    *,
    scenario: str = "sso",
    auto_decide: bool = False,
    offline: bool = False,
    keep: bool = False,
    followup: bool = False,
    recovery: bool = False,
) -> RecoveryReport | None:
    validate_options(
        scenario=scenario, auto_decide=auto_decide, followup=followup, recovery=recovery
    )
    if scenario not in seed.ALL_SCENARIOS:
        raise SplitbrainError(f"Unknown demo scenario {scenario!r}")
    paths = Paths.default()
    modes = resolve_modes(offline=offline, scenario=scenario, paths=paths)
    loaded = seed.load_scenario(Settings.load(require_env_file=False), scenario)
    effective_auto = auto_decide and loaded.decision is not None
    if followup and (scenario != "sso" or not effective_auto):
        raise SplitbrainError("--followup requires --scenario sso and --auto-decide.")
    print("=" * 72, flush=True)
    followup_tag = " | followup=yes" if followup else ""
    recovery_tag = " | recovery=yes" if recovery else ""
    print(
        f"Splitbrain demo: scenario={scenario} | auto-decide={'yes' if effective_auto else 'no'}"
        f" | offline={'yes' if offline else 'no'} | keep={'yes' if keep else 'no'}"
        f"{followup_tag}{recovery_tag}",
        flush=True,
    )
    modes.print_banners()
    if auto_decide and not effective_auto:
        print(
            "[demo] This scenario has no 'decision:' block: it stops at the conflict room, "
            "no automatic decision is needed.",
            flush=True,
        )
    print("=" * 72, flush=True)

    settings, clean_description = await prepare_clean_state(keep=keep)
    modes = replace(modes, clean_state=clean_description)
    state = await bootstrap.run(settings)
    env = child_environment(modes)
    if recovery:
        env[demo_faults.ENV_VAR] = demo_faults.SENTINEL_AFTER_FIRST
    group = await start_agents(paths.root, env, settings=settings, state=state)
    observer: SwitchAgent | None = None
    recovery_demo: RecoveryDemo | None = None
    try:
        observer = await _observer(settings, state)
        ops_id = state.rooms["splitbrain-ops"].room_id
        await _wait_for_agents(group, observer, state)
        existing_conflicts = await seed._conflict_rooms(observer)
        seed_options: dict[str, Any] = {}
        if recovery:
            assert loaded.decision is not None
            recovery_demo = RecoveryDemo(
                settings, state, group, observer, paths.root, env, loaded.decision
            )
            await recovery_demo.start()
            seed_options["decision_hooks"] = recovery_demo
        result = await seed.run(settings, scenario, auto_decide=effective_auto, **seed_options)
        if not effective_auto and loaded.decision is not None:
            # Printed before waiting for the room: consent must be granted first.
            print_consent_instructions(loaded, state, settings)
        conflict_room = result.conflict_room_name
        if conflict_room is None:
            conflict_room = await _wait_for_conflict(
                group,
                observer,
                existing_conflicts,
                CONFLICT_TIMEOUT_S if effective_auto else HUMAN_CONFLICT_TIMEOUT_S,
            )
        _, brief = await _wait_for_brief(group, observer, conflict_room, BRIEF_TIMEOUT_S)

        decision: dict[str, Any] | None = None
        corrections: list[str] = []
        followup_summary: str | None = None
        note = "conflict room created with both quotes"
        if effective_auto:
            decided = await _wait_for_packet(group, observer, ops_id, "decided", PACKET_TIMEOUT_S)
            decision = decided.get("decision", {})
            corrected = await _wait_for_packet(
                group, observer, ops_id, "corrected", PACKET_TIMEOUT_S
            )
            corrections = list(corrected.get("rooms", []))
            note = "full loop closed by --auto-decide (decision + corrections)"
            if followup:
                await seed.run(settings, "sso-followup")
                reminded = await _wait_for_packet(
                    group, observer, ops_id, "reminded", PACKET_TIMEOUT_S
                )
                await _wait_for_followup_silence(group)
                room = str(reminded.get("room_name") or "support")
                person = bootstrap.DEMO_USER_DISPLAY_NAMES.get(
                    str(reminded.get("author") or "lucia"), "Lucía Pérez"
                )
                followup_summary = (
                    f"reminder posted in #{room} for {person}; "
                    "Pablo Ruiz's compatible message stayed silent"
                )
        elif loaded.decision is not None:
            print_decision_instructions(loaded, conflict_room, settings)
            decision, corrections = await _wait_for_human_close(
                group, observer, ops_id, conflict_room
            )
            note = "decided by people in Mattermost; corrections propagated"
        else:
            missing = [message.person for message in loaded.messages if message.text not in brief]
            if missing:
                raise SplitbrainError(
                    f"The brief in #{conflict_room} is missing the quote(s) from "
                    f"{', '.join(missing)}."
                )
            note = "conflict room created with both public-page quotes; no decision requested"

        if recovery_demo is not None and recovery_demo.report is None:
            raise SplitbrainError(
                "Recovery expected all three verified outcomes; observed no report"
            )
        print_summary(
            settings=settings,
            state=state,
            modes=modes,
            scenario=scenario,
            conflict_room=conflict_room,
            decision=decision,
            corrections=corrections,
            note=note,
            followup_summary=followup_summary,
        )
        if recovery_demo is not None:
            assert recovery_demo.report is not None
            recovery_demo.report.print_summary()
            return recovery_demo.report
        return None
    finally:
        if recovery_demo is not None:
            await recovery_demo.aclose()
        if observer is not None:
            await observer.aclose()
        await group.stop()


async def run_agents(settings: Settings) -> None:
    """`run all`: the four agents as subprocesses until Ctrl+C."""
    group = await start_agents(
        settings.paths.root,
        os.environ.copy(),
        settings=settings,
        state=bootstrap.load_state(settings),
    )
    print("[run all] four agents running. Press Ctrl+C to stop them.", flush=True)
    try:
        while True:
            group.check()
            await asyncio.sleep(POLL_S)
    finally:
        await group.stop()
