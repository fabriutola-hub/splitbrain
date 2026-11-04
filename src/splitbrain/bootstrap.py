"""Idempotent bootstrap for the Splitbrain demo stack."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Any, Protocol

import httpx
import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings, SplitbrainError, loopback_client, redact
from .switch.client import SwitchAgent
from .switch.events import ConnectionStateFrame, SwitchFrame
from .switch.gateway import GatewayAdmin
from .switch.mattermost import MattermostAdmin

AGENT_NAMES = (
    "splitbrain-sentinel",
    "splitbrain-arbiter",
    "splitbrain-verifier",
    "splitbrain-arbiter-b",
)
DEMO_USERS = (
    "maria",
    "tomas",
    "lucia",
    "pablo",
    "fabrizio",
    "page-prizes",
    "page-judging",
)
# Mattermost renders full_name by default in this stack; make the two public
# pages readable in the UI instead of "Integration Probe".
DEMO_USER_DISPLAY_NAMES = {
    "maria": "María Gómez",
    "tomas": "Tomás Rivera",
    "lucia": "Lucía Pérez",
    "pablo": "Pablo Ruiz",
    "fabrizio": "Fabrizio U.",
    "page-prizes": "Prizes page",
    "page-judging": "Judging page",
}
TEAM_ROOMS = ("sales", "engineering", "support", "finance")
OPS_ROOM = "splitbrain-ops"
ALL_ROOMS = (*TEAM_ROOMS, OPS_ROOM)
HACKATHON_ROOMS = ("hackathon-prizes", "hackathon-judging")
HACKATHON_GROUP = "Flip the Switch"
STATE_ROOMS = (*ALL_ROOMS, *HACKATHON_ROOMS)
GROUP_NAME = "Acme"
REFERENCE_NAME = "Acme roadmap"
DEFAULT_ROADMAP_REPO = "https://github.com/fabriutola-hub/splitbrain-demo-roadmap"
STATE_FILE = "state.json"
TEMPLATE_FILE = "splitbrain.template.yaml"
HACKATHON_TEMPLATE_FILE = "hackathon.template.yaml"


class AgentState(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_id: str
    api_key: str


class RoomState(BaseModel):
    model_config = ConfigDict(extra="allow")

    room_id: str
    channel_type: str
    group_name: str | None = None


class MattermostState(BaseModel):
    model_config = ConfigDict(extra="allow")

    password: str
    users: list[str] = Field(default_factory=list)


class ReferenceState(BaseModel):
    model_config = ConfigDict(extra="allow")

    reference_id: str
    name: str
    attached_room_id: str


class BootstrapState(BaseModel):
    model_config = ConfigDict(extra="allow")

    agents: dict[str, AgentState] = Field(default_factory=dict)
    rooms: dict[str, RoomState] = Field(default_factory=dict)
    group: str | None = None
    group_id: str | None = None
    mattermost: MattermostState | None = None
    reference: ReferenceState | None = None
    addressing_open_for: dict[str, str] = Field(default_factory=dict)


class OperationClient(Protocol):
    async def op(self, name: str, /, **args: Any) -> Any: ...


def state_path(settings: Settings) -> Path:
    return settings.paths.state_dir / STATE_FILE


def load_state(settings: Settings) -> BootstrapState:
    path = state_path(settings)
    if not path.is_file():
        return BootstrapState()
    return BootstrapState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(settings: Settings, state: BootstrapState) -> None:
    directory = settings.paths.state_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / STATE_FILE
    path.write_text(json.dumps(state.model_dump(), indent=2) + "\n", encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o600)


def template_text(settings: Settings, filename: str = TEMPLATE_FILE) -> str:
    path = settings.paths.root / "templates" / filename
    if not path.is_file():
        raise SplitbrainError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def template_inputs(settings: Settings) -> dict[str, str]:
    folder = settings.paths.root / "agents"
    inputs: dict[str, str] = {}
    for key, filename in (
        ("arbiter_instructions", "arbiter.md"),
        ("verifier_instructions", "verifier.md"),
    ):
        path = folder / filename
        if not path.is_file():
            raise SplitbrainError(f"Missing role instructions: {path}")
        inputs[key] = path.read_text(encoding="utf-8")
    return inputs


def expected_channel_types(settings: Settings) -> dict[str, str]:
    document = yaml.safe_load(template_text(settings))
    return {
        str(room["name"]): str(room.get("channel_type", "channel_public"))
        for room in document["rooms"]
    }


def roadmap_repo(settings: Settings) -> str:
    """Process env > .env.local > the verified demo repo in SPEC 4.5."""
    local = dotenv_values(settings.paths.root / ".env.local")
    value = (
        os.environ.get("SPLITBRAIN_ROADMAP_REPO")
        or local.get("SPLITBRAIN_ROADMAP_REPO")
        or DEFAULT_ROADMAP_REPO
    )
    if not isinstance(value, str) or not value.strip():
        raise SplitbrainError("SPLITBRAIN_ROADMAP_REPO is empty")
    return value.strip()


async def _agent_is_live(client: httpx.AsyncClient, settings: Settings, creds: AgentState) -> bool:
    response = await client.get(
        f"{settings.api_base_url}/agents/{creds.agent_id}/ops",
        headers={"Authorization": f"Bearer {creds.api_key}"},
    )
    if response.status_code == 200:
        return True
    if response.status_code in (401, 403, 404):
        return False
    raise SplitbrainError(
        f"Checking agent {creds.agent_id} returned {response.status_code}: "
        f"{redact(response.text, (creds.api_key,))}"
    )


async def ensure_agents(
    settings: Settings, state: BootstrapState, *, client: httpx.AsyncClient
) -> None:
    token = settings.values.get("AGENT_REGISTRATION_TOKEN", "").strip()
    if not token:
        raise SplitbrainError("AGENT_REGISTRATION_TOKEN is missing from deploy/.env")
    for name in AGENT_NAMES:
        existing = state.agents.get(name)
        if existing is not None and await _agent_is_live(client, settings, existing):
            continue
        credentials = await SwitchAgent.register(
            settings.api_base_url,
            token,
            name,
            f"Splitbrain {name.removeprefix('splitbrain-')} agent",
            overwrite=True,
            client=client,
        )
        state.agents[name] = AgentState(agent_id=credentials.agent_id, api_key=credentials.api_key)


async def ensure_people(
    settings: Settings, state: BootstrapState, *, admin: MattermostAdmin
) -> None:
    await admin.login()
    if state.mattermost is None:
        state.mattermost = MattermostState(password=secrets.token_urlsafe(12))
        # Persist the password before creating users: a later failure must not
        # leave accounts whose credential was never written down.
        save_state(settings, state)
    for username in DEMO_USERS:
        user = await admin.ensure_user(
            username,
            state.mattermost.password,
            display_name=DEMO_USER_DISPLAY_NAMES.get(username),
        )
        await user.aclose()
        if username not in state.mattermost.users:
            state.mattermost.users.append(username)


async def ensure_gateway(
    settings: Settings, state: BootstrapState, *, gateway: GatewayAdmin
) -> None:
    await gateway.login()
    bridges = await gateway.bridges()
    bridge = next(
        (item for item in bridges if item.is_default),
        None,
    ) or next((item for item in bridges if item.display_name == "Mattermost"), None)
    if bridge is None:
        raise SplitbrainError("No Mattermost bridge found in the Gateway")
    if bridge.agent_greetings_enabled:
        await gateway.set_greetings(bridge.bridge_id, False)
    for name, creds in state.agents.items():
        if state.addressing_open_for.get(name) == creds.agent_id:
            continue
        await gateway.open_addressing(creds.agent_id)
        state.addressing_open_for[name] = creds.agent_id


async def _all_rooms(agent: OperationClient) -> dict[str, str]:
    # The 0.31.0 image accepts only `include_archived` here (no limit/cursor),
    # and older builds answer with a bare list. Read the live registry before
    # adding arguments to this call.
    page = await agent.op("list_all_rooms")
    rooms = page if isinstance(page, list) else page.get("rooms", [])
    return {str(room["name"]): str(room["room_id"]) for room in rooms}


def _extract_values(entries: Any, keys: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str):
            result.add(entry)
        elif isinstance(entry, dict):
            for key in keys:
                value = entry.get(key)
                if isinstance(value, str):
                    result.add(value)
                    break
    return result


async def _ensure_ops_members_and_links(agent: OperationClient, state: BootstrapState) -> None:
    ops_id = state.rooms[OPS_ROOM].room_id
    detail = await agent.op("get_room_detail", room_id=ops_id)
    present = set(detail.get("agent_names") or [])
    for name in AGENT_NAMES:
        if name not in present:
            await agent.op("invite_agent_to_room", room_id=ops_id, agent_name=name)

    context = await agent.op("connect_to_room", room_id=ops_id)
    linked = _extract_values(
        context.get("linked_rooms"), ("target_room_id", "room_id", "id", "linked_room_id")
    )
    for name in TEAM_ROOMS:
        target = state.rooms[name].room_id
        if target not in linked:
            await agent.op(
                "link_rooms", source_room_id=ops_id, target_room_id=target, label="watches"
            )


async def ensure_rooms(agent: OperationClient, settings: Settings, state: BootstrapState) -> None:
    channel_types = expected_channel_types(settings)
    existing = await _all_rooms(agent)
    found = {name: existing[name] for name in ALL_ROOMS if name in existing}
    if found and len(found) != len(ALL_ROOMS):
        missing = sorted(set(ALL_ROOMS) - set(found))
        raise SplitbrainError(
            f"Partial Acme group found ({sorted(found)}); missing {missing}. "
            "Refusing to provision again to avoid duplicate rooms."
        )

    if found:
        for name, room_id in found.items():
            detail = await agent.op("get_room_detail", room_id=room_id)
            state.rooms[name] = RoomState(
                room_id=room_id,
                channel_type=str(detail.get("channel_type") or channel_types[name]),
                group_name=detail.get("group_name"),
            )
        state.group = state.rooms[OPS_ROOM].group_name or GROUP_NAME
    else:
        result = await agent.op(
            "create_room_from_yaml", yaml=template_text(settings), inputs=template_inputs(settings)
        )
        errors = result.get("errors") or []
        if errors:
            raise SplitbrainError(f"create_room_from_yaml reported errors: {errors}")
        for room in result.get("rooms", []):
            failures = room.get("failed_attachments") or []
            if failures:
                raise SplitbrainError(
                    f"Room {room.get('room_name')} has failed attachments: {failures}"
                )
            name = str(room["room_name"])
            state.rooms[name] = RoomState(
                room_id=str(room["room_id"]),
                channel_type=channel_types[name],
                group_name=GROUP_NAME,
            )
        state.group = str(result.get("group_name") or GROUP_NAME)
        state.group_id = result.get("group_id")

    missing = sorted(set(ALL_ROOMS) - set(state.rooms))
    if missing:
        raise SplitbrainError(f"Template did not create the expected rooms: {missing}")
    await _ensure_ops_members_and_links(agent, state)


async def ensure_hackathon_rooms(
    agent: OperationClient, settings: Settings, state: BootstrapState
) -> None:
    """M7: the two public pages, created by their own template, idempotently."""
    existing = await _all_rooms(agent)
    found = {name: existing[name] for name in HACKATHON_ROOMS if name in existing}
    if found and len(found) != len(HACKATHON_ROOMS):
        raise SplitbrainError(
            f"Partial hackathon group found ({sorted(found)}); "
            f"missing {sorted(set(HACKATHON_ROOMS) - set(found))}. "
            "Refusing to provision again to avoid duplicate rooms."
        )
    if found:
        for name, room_id in found.items():
            detail = await agent.op("get_room_detail", room_id=room_id)
            state.rooms[name] = RoomState(
                room_id=room_id,
                channel_type=str(detail.get("channel_type") or "channel_public"),
                group_name=detail.get("group_name") or HACKATHON_GROUP,
            )
        return

    text = template_text(settings, HACKATHON_TEMPLATE_FILE)
    document = yaml.safe_load(text)
    channel_types = {
        str(room["name"]): str(room.get("channel_type", "channel_public"))
        for room in document["rooms"]
    }
    result = await agent.op("create_room_from_yaml", yaml=text, inputs={})
    errors = result.get("errors") or []
    if errors:
        raise SplitbrainError(f"Hackathon template reported errors: {errors}")
    for room in result.get("rooms", []):
        failures = room.get("failed_attachments") or []
        if failures:
            raise SplitbrainError(
                f"Room {room.get('room_name')} has failed attachments: {failures}"
            )
        name = str(room["room_name"])
        if name not in HACKATHON_ROOMS:
            raise SplitbrainError(f"Hackathon template created unexpected room {name!r}")
        state.rooms[name] = RoomState(
            room_id=str(room["room_id"]),
            channel_type=channel_types[name],
            group_name=str(result.get("group_name") or HACKATHON_GROUP),
        )
    missing = sorted(set(HACKATHON_ROOMS) - set(state.rooms))
    if missing:
        raise SplitbrainError(f"Hackathon template did not create the expected rooms: {missing}")


async def ensure_reference(
    agent: OperationClient, settings: Settings, state: BootstrapState
) -> None:
    types = await agent.op("list_reference_types")
    slugs = _extract_values(types, ("type",))
    if "github" not in slugs:
        raise SplitbrainError(f"github is not an available reference type: {sorted(slugs)}")

    url = roadmap_repo(settings)
    refs = await agent.op("list_all_references", name_contains=REFERENCE_NAME, type="github")
    reference = next((item for item in refs if item.get("name") == REFERENCE_NAME), None)
    if reference is None:
        reference = await agent.op(
            "create_reference",
            type="github",
            name=REFERENCE_NAME,
            description="Public fictional roadmap used as independent demo evidence",
            instructions=(
                "Read the issues and their milestone history for the subject of a claim. "
                "Report titles, states, milestones and milestone moves. Ignore closed duplicates."
            ),
            value={"urls": [url]},
        )
    reference_id = str(reference["id"])
    ops_id = state.rooms[OPS_ROOM].room_id
    context = await agent.op("connect_to_room", room_id=ops_id)
    attached = _extract_values(context.get("references"), ("id", "reference_id"))
    if reference_id not in attached:
        await agent.op("attach_reference_to_room", room_id=ops_id, reference_id=reference_id)
    state.reference = ReferenceState(
        reference_id=reference_id, name=REFERENCE_NAME, attached_room_id=ops_id
    )


def print_summary(state: BootstrapState) -> None:
    print(f"Bootstrap complete. Group: {state.group or GROUP_NAME}")
    print(f"Agents: {', '.join(sorted(state.agents))}")
    print("Rooms:")
    for name in STATE_ROOMS:
        room = state.rooms.get(name)
        if room is not None:
            print(f"  {name:<20} {room.channel_type:<18} {room.room_id}")
    if state.reference:
        print(f"Reference: {state.reference.name} attached to {OPS_ROOM}")
    if state.mattermost:
        print("Mattermost demo logins (team switch, shared password):")
        for username in DEMO_USERS:
            print(f"  {username:<14} {state.mattermost.password}")


async def run(settings: Settings) -> BootstrapState:
    state = load_state(settings)
    async with loopback_client(timeout=10.0) as client:
        await ensure_agents(settings, state, client=client)
        save_state(settings, state)

        admin = MattermostAdmin(
            settings.mattermost_url,
            settings.values["MATTERMOST_ADMIN_USER"],
            settings.values["MATTERMOST_ADMIN_PASSWORD"],
            settings.values.get("MATTERMOST_TEAM_NAME", "switch"),
        )
        try:
            await ensure_people(settings, state, admin=admin)
            save_state(settings, state)
        finally:
            await admin.aclose()

        gateway = GatewayAdmin(
            settings.api_base_url,
            settings.gateway_admin_email,
            settings.gateway_admin_password,
        )
        try:
            await ensure_gateway(settings, state, gateway=gateway)
            save_state(settings, state)
        finally:
            await gateway.aclose()

        sentinel = state.agents["splitbrain-sentinel"]
        agent = SwitchAgent(settings.api_base_url, sentinel.agent_id, sentinel.api_key)
        # Switch refuses ops whose connection id has no open stream (409), so
        # bootstrap keeps one short-lived Sentinel connection for the whole run.
        state_ready = asyncio.Event()
        stop = asyncio.Event()

        async def handler(frame: SwitchFrame) -> None:
            if isinstance(frame, ConnectionStateFrame):
                state_ready.set()

        stream_task = asyncio.create_task(agent.run(handler, stop=stop))
        try:
            await asyncio.wait_for(state_ready.wait(), timeout=20.0)
            await ensure_rooms(agent, settings, state)
            save_state(settings, state)
            await ensure_hackathon_rooms(agent, settings, state)
            save_state(settings, state)
            await ensure_reference(agent, settings, state)
            save_state(settings, state)
        finally:
            stop.set()
            stream_task.cancel()
            await asyncio.gather(stream_task, return_exceptions=True)
            await agent.aclose()

    save_state(settings, state)
    print_summary(state)
    return state


async def print_status(settings: Settings) -> None:
    state = load_state(settings)
    if not state.agents or not state.rooms:
        print("bootstrap: not run yet (uv run splitbrain bootstrap)")
        return
    print(f"group: {state.group or GROUP_NAME}")
    print(f"agents: {', '.join(sorted(state.agents))}")
    print("rooms:")
    for name in STATE_ROOMS:
        room = state.rooms.get(name)
        if room is not None:
            print(f"  {name:<20} {room.channel_type:<18} {room.room_id}")
    print(f"reference: {state.reference.name if state.reference else 'none'}")
    ops = state.rooms.get(OPS_ROOM)
    sentinel = state.agents.get("splitbrain-sentinel")
    if ops is not None and sentinel is not None:
        agent = SwitchAgent(settings.api_base_url, sentinel.agent_id, sentinel.api_key)
        try:
            detail = await agent.op("get_room_detail", room_id=ops.room_id, connection=False)
            holders: list[str] = []
            for role in detail.get("roles", []):
                if role.get("name") != "arbiter":
                    continue
                for holder in role.get("held_by") or []:
                    name = holder.get("name") if isinstance(holder, dict) else holder
                    if name:
                        holders.append(str(name))
            print(f"arbiter role: {', '.join(holders) if holders else 'unheld'}")
        finally:
            await agent.aclose()
