"""Post a demo scenario as its people and, with --auto-decide, drive the loop.

`--auto-decide` answers the Sentinel's consent question as the private-room
author, then posts the scenario's `decision:` / `confirm` pair in the conflict
room once it exists. Every wait has an explicit timeout and says what it expected.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import bootstrap
from .config import Settings, SplitbrainError
from .core.store import ClaimStore
from .switch.client import SwitchAgent
from .switch.mattermost import MattermostError, MattermostUser, Post

SCENARIO_DIR = Path("seed") / "scenarios"
ALL_SCENARIOS: tuple[str, ...] = ("sso", "refunds", "hackathon", "near-misses")
CHANNEL_TIMEOUT_S = 10.0
CONSENT_QUESTION_TIMEOUT_S = 120.0
CONFLICT_ROOM_TIMEOUT_S = 180.0
BRIEF_TIMEOUT_S = 90.0
CORRECTIONS_TIMEOUT_S = 120.0
POLL_S = 0.5

CONSENT_QUESTION_MARKER = "May I quote it in a private resolution room"
BRIEF_MARKER = "Splitbrain found two statements"
CORRECTIONS_MARKER = "Corrections posted"


class SeedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    room: str
    person: str = Field(alias="as")
    after_s: float = Field(default=0.0, ge=0.0)
    text: str


class SeedDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    propose: dict[str, str]
    confirm: dict[str, str]


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    people: dict[str, str] = Field(default_factory=dict)
    messages: list[SeedMessage] = Field(default_factory=list)
    decision: SeedDecision | None = None


@dataclass(frozen=True, slots=True)
class PostedMessage:
    message: SeedMessage
    post_id: str
    channel_id: str


@dataclass(frozen=True, slots=True)
class SeedResult:
    scenario: str
    posted: list[PostedMessage]
    conflict_room_name: str | None = None


def scenario_path(settings: Settings, name: str) -> Path:
    folder = settings.paths.root / SCENARIO_DIR
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise SplitbrainError(f"Invalid scenario name: {name!r}")
    return folder / f"{name}.yaml"


def load_scenario(settings: Settings, name: str) -> Scenario:
    path = scenario_path(settings, name)
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in path.parent.glob("*.yaml"))) or "none"
        raise SplitbrainError(f"Unknown scenario {name!r}. Available: {available}.")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SplitbrainError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SplitbrainError(f"{path} must contain a YAML mapping")
    try:
        scenario = Scenario.model_validate(data)
    except ValueError as exc:
        raise SplitbrainError(f"Invalid scenario {path}: {exc}") from exc
    if scenario.name != name:
        raise SplitbrainError(f"{path} declares name={scenario.name!r}, expected {name!r}")
    if not scenario.messages:
        raise SplitbrainError(f"{path} has no messages")
    unknown = sorted({message.person for message in scenario.messages} - set(scenario.people))
    if unknown:
        raise SplitbrainError(f"{path} uses people missing from 'people': {', '.join(unknown)}")
    return scenario


def synthetic_state() -> bootstrap.BootstrapState:
    """Room map for the offline pipeline (record / replay tests), no Switch."""
    return bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(
                room_id=f"r-{name}",
                channel_type="channel_private"
                if name in ("engineering", "splitbrain-ops")
                else "channel_public",
            )
            for name in bootstrap.STATE_ROOMS
        }
    )


async def check_stale_claims(settings: Settings, scenario: Scenario) -> None:
    """Refuse a re-seed when an earlier run left active claims in these rooms.

    M6 showed the failure mode: an old active claim pairs with the new message
    and produces a second candidate whose correction lands in the old thread.
    """
    from .agents import sentinel as sentinel_agent  # local: DB_FILENAME is patchable

    state_dir = getattr(settings.paths, "state_dir", None)
    if state_dir is None:
        return
    db_path = Path(state_dir) / sentinel_agent.DB_FILENAME
    if not db_path.is_file():
        return
    store = ClaimStore(db_path)
    try:
        active = await store.active_claims()
    finally:
        await store.close()
    rooms = {message.room for message in scenario.messages}
    people = set(scenario.people)
    stale = [
        claim
        for claim in active
        if claim.room_name in rooms
        and claim.author in people
        and not claim.room_name.startswith("conflict-")
    ]
    if not stale:
        return
    sample = ", ".join(
        f"#{claim.room_name}/{claim.author}: {claim.subject_key}" for claim in stale[:4]
    )
    raise SplitbrainError(
        f"Sentinel still holds {len(stale)} active claim(s) from an earlier run of "
        f"scenario {scenario.name!r} ({sample}). Re-seeding would pair them with the new "
        "messages and create a second, stale conflict. Clean up first:\n"
        "  uv run splitbrain demo                  # wipes the stack and starts clean\n"
        "  uv run splitbrain down --wipe && uv run splitbrain up && uv run splitbrain bootstrap\n"
        "or delete just .splitbrain/sentinel.db (then restart the Sentinel)."
    )


async def _channel(user: MattermostUser, room: str) -> str:
    """The bridged channel can take a moment to appear for a freshly added user."""
    deadline = time.monotonic() + CHANNEL_TIMEOUT_S
    while True:
        try:
            return await user.channel_for_room(room)
        except MattermostError as exc:
            if exc.status != 404 or time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.4)


async def _wait_for(description: str, timeout_s: float, poll: Callable[[], Awaitable[Any]]) -> Any:
    """Poll until the expected artifact appears, or fail saying what we wanted."""
    deadline = time.monotonic() + timeout_s
    while True:
        value = await poll()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                f"Timed out after {timeout_s:.0f}s waiting for {description}. "
                "Check that sentinel, arbiter, verifier (and arbiter-b) are running and "
                "that the scenario really produced a candidate."
            )
        await asyncio.sleep(POLL_S)


async def _find_in_thread(user: MattermostUser, post_id: str, marker: str) -> Post | None:
    try:
        posts = await user.thread(post_id)
    except MattermostError as exc:
        if exc.status == 404:
            return None
        raise
    return next((post for post in posts if marker in post.message), None)


async def _find_in_channel(user: MattermostUser, channel_id: str, marker: str) -> Post | None:
    try:
        posts = await user.channel_posts(channel_id)
    except MattermostError as exc:
        if exc.status == 404:
            return None
        raise
    return next((post for post in posts if marker in post.message), None)


async def _channel_or_none(user: MattermostUser, room: str) -> str | None:
    try:
        return await user.channel_for_room(room)
    except MattermostError as exc:
        if exc.status == 404:
            return None
        raise


async def _conflict_rooms(agent: SwitchAgent) -> set[str]:
    rooms = await agent.op("list_all_rooms", connection=False)
    entries = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
    return {
        str(entry["name"])
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("name") or "").startswith("conflict-")
    }


async def _user(
    users: dict[str, MattermostUser],
    settings: Settings,
    person: str,
    password: str,
    team: str,
) -> MattermostUser:
    if person not in users:
        users[person] = await MattermostUser.login(settings.mattermost_url, person, password, team)
    return users[person]


async def _auto_decide(
    settings: Settings,
    scenario: Scenario,
    state: bootstrap.BootstrapState,
    users: dict[str, MattermostUser],
    posted: list[PostedMessage],
    existing_conflicts: set[str],
    password: str,
    team: str,
) -> str:
    if scenario.decision is None:
        raise SplitbrainError(
            f"Scenario {scenario.name!r} has no 'decision:' block for --auto-decide."
        )
    decision = scenario.decision
    sentinel = state.agents.get("splitbrain-sentinel")
    if sentinel is None:
        raise SplitbrainError("No Sentinel credentials; run 'uv run splitbrain bootstrap'.")
    agent = SwitchAgent(settings.api_base_url, sentinel.agent_id, sentinel.api_key)
    try:
        private_rooms = {
            name for name, room in state.rooms.items() if room.channel_type == "channel_private"
        }
        private_posts = [item for item in posted if item.message.room in private_rooms]

        if private_posts:
            target = private_posts[0]
            answerer = await _user(users, settings, target.message.person, password, team)
            question = await _wait_for(
                f"the consent question in #{target.message.room} thread {target.post_id} "
                f"(expected the Sentinel to ask @{target.message.person} to quote their "
                "private message)",
                CONSENT_QUESTION_TIMEOUT_S,
                lambda: _find_in_thread(answerer, target.post_id, CONSENT_QUESTION_MARKER),
            )
            print(
                f"  [auto-decide] consent question found: {question.message[:90]}...",
                flush=True,
            )
            await answerer.reply(target.channel_id, target.post_id, "yes")
            print(f"  [auto-decide] answered 'yes' as @{target.message.person}.", flush=True)
        else:
            print(
                "  [auto-decide] no private-room claim; no consent question expected.", flush=True
            )

        async def new_conflict() -> str | None:
            current = await _conflict_rooms(agent)
            fresh = sorted(current - existing_conflicts)
            return fresh[0] if fresh else None

        room_name = await _wait_for(
            "a NEW conflict-* room (expected the Arbiter to create it after the "
            "verdict and the consent answer)",
            CONFLICT_ROOM_TIMEOUT_S,
            new_conflict,
        )
        print(f"  [auto-decide] conflict room #{room_name} exists.", flush=True)

        proposer = decision.propose["as"]
        confirmer = decision.confirm["as"]
        first = await _user(users, settings, proposer, password, team)
        second = await _user(users, settings, confirmer, password, team)
        channel_id = await _wait_for(
            f"the Mattermost channel for #{room_name} to appear for @{proposer}",
            BRIEF_TIMEOUT_S,
            lambda: _channel_or_none(first, room_name),
        )
        await _wait_for(
            f"the Arbiter's brief in #{room_name} (expected '{BRIEF_MARKER}')",
            BRIEF_TIMEOUT_S,
            lambda: _find_in_channel(first, channel_id, BRIEF_MARKER),
        )
        await first.post(channel_id, decision.propose["text"])
        print(f"  [auto-decide] @{proposer}: {decision.propose['text']}", flush=True)
        await asyncio.sleep(0.5)
        await second.post(channel_id, decision.confirm["text"])
        print(f"  [auto-decide] @{confirmer}: {decision.confirm['text']}", flush=True)

        await _wait_for(
            f"the final '{CORRECTIONS_MARKER}' confirmation in #{room_name} (expected "
            "the Arbiter to close the loop after the Sentinel corrected both threads)",
            CORRECTIONS_TIMEOUT_S,
            lambda: _find_in_channel(first, channel_id, CORRECTIONS_MARKER),
        )
        print("  [auto-decide] corrections posted; full loop closed.", flush=True)
        return room_name
    finally:
        await agent.aclose()


async def run(settings: Settings, name: str, *, auto_decide: bool = False) -> SeedResult:
    scenario = load_scenario(settings, name)
    if auto_decide and scenario.decision is None:
        raise SplitbrainError(
            f"Scenario {name!r} has no 'decision:' block, so --auto-decide cannot close a conflict."
        )
    await check_stale_claims(settings, scenario)
    state = bootstrap.load_state(settings)
    if state.mattermost is None or not state.mattermost.password:
        raise SplitbrainError("Run 'uv run splitbrain bootstrap' before seeding a scenario.")

    password = state.mattermost.password
    team = settings.values.get("MATTERMOST_TEAM_NAME", "switch")
    total = len(scenario.messages)
    existing_conflicts: set[str] = set()
    if auto_decide:
        sentinel = state.agents.get("splitbrain-sentinel")
        if sentinel is None:
            raise SplitbrainError("No Sentinel credentials; run 'uv run splitbrain bootstrap'.")
        observer = SwitchAgent(settings.api_base_url, sentinel.agent_id, sentinel.api_key)
        try:
            existing_conflicts = await _conflict_rooms(observer)
        finally:
            await observer.aclose()

    print(f"Seeding scenario {name!r}: {total} messages as its people.", flush=True)
    users: dict[str, MattermostUser] = {}
    posted: list[PostedMessage] = []
    try:
        for index, message in enumerate(scenario.messages, start=1):
            if message.after_s:
                await asyncio.sleep(message.after_s)
            user = await _user(users, settings, message.person, password, team)
            channel_id = await _channel(user, message.room)
            post_id = await user.post(channel_id, message.text)
            posted.append(PostedMessage(message=message, post_id=post_id, channel_id=channel_id))
            print(
                f"  [{index}/{total}] #{message.room:<12} {message.person:<8} {message.text}",
                flush=True,
            )
        conflict_room_name: str | None = None
        if auto_decide:
            conflict_room_name = await _auto_decide(
                settings,
                scenario,
                state,
                users,
                posted,
                existing_conflicts,
                password,
                team,
            )
        print(f"Scenario {name!r} posted ({total} messages).", flush=True)
        return SeedResult(scenario=name, posted=posted, conflict_room_name=conflict_room_name)
    finally:
        for user in users.values():
            await user.aclose()
