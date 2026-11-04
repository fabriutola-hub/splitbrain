"""Post a demo scenario's messages as its people through the Mattermost API.

M4 implements `seed <scenario>` only. `--auto-decide` needs the Arbiter's
conflict room and belongs to M5, so it fails loudly instead of half-working.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import bootstrap
from .config import Settings, SplitbrainError
from .switch.mattermost import MattermostError, MattermostUser

SCENARIO_DIR = Path("seed") / "scenarios"
CHANNEL_TIMEOUT_S = 10.0


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


async def run(settings: Settings, name: str, *, auto_decide: bool = False) -> None:
    if auto_decide:
        raise SplitbrainError(
            "--auto-decide is M5: it needs the Arbiter's conflict room, which M4 does not create."
        )
    scenario = load_scenario(settings, name)
    state = bootstrap.load_state(settings)
    if state.mattermost is None or not state.mattermost.password:
        raise SplitbrainError("Run 'uv run splitbrain bootstrap' before seeding a scenario.")

    password = state.mattermost.password
    team = settings.values.get("MATTERMOST_TEAM_NAME", "switch")
    total = len(scenario.messages)
    print(f"Seeding scenario {name!r}: {total} messages as its people.", flush=True)
    users: dict[str, MattermostUser] = {}
    try:
        for index, message in enumerate(scenario.messages, start=1):
            if message.after_s:
                await asyncio.sleep(message.after_s)
            if message.person not in users:
                users[message.person] = await MattermostUser.login(
                    settings.mattermost_url, message.person, password, team
                )
            channel_id = await _channel(users[message.person], message.room)
            await users[message.person].post(channel_id, message.text)
            print(
                f"  [{index}/{total}] #{message.room:<12} {message.person:<8} {message.text}",
                flush=True,
            )
    finally:
        for user in users.values():
            await user.aclose()
    print(f"Scenario {name!r} posted ({total} messages).", flush=True)
