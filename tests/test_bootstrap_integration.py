"""M2 integration: bootstrap the live stack and verify the result through APIs."""

from __future__ import annotations

import asyncio

import pytest

from splitbrain import bootstrap
from splitbrain.config import Settings
from splitbrain.switch.client import SwitchAgent
from splitbrain.switch.events import ConnectionStateFrame, SwitchFrame
from splitbrain.switch.gateway import GatewayAdmin
from splitbrain.switch.mattermost import MattermostUser

pytestmark = pytest.mark.integration


async def test_bootstrap_provisions_the_acme_group_once() -> None:
    settings = Settings.load()
    state = await bootstrap.run(settings)  # idempotent: safe after the CLI ran it

    assert set(state.agents) == set(bootstrap.AGENT_NAMES)
    assert set(state.rooms) == set(bootstrap.STATE_ROOMS)
    assert state.group == "Acme"
    assert state.reference is not None and state.reference.name == "Acme roadmap"
    assert state.mattermost is not None
    assert set(state.mattermost.users) == set(bootstrap.DEMO_USERS)

    sentinel = state.agents["splitbrain-sentinel"]
    agent = SwitchAgent(settings.api_base_url, sentinel.agent_id, sentinel.api_key)
    try:
        all_rooms = await agent.op("list_all_rooms", connection=False)
        names = [str(room["name"]) for room in all_rooms]
        for name in bootstrap.STATE_ROOMS:
            assert names.count(name) == 1, f"duplicate room {name}"

        for name, room in state.rooms.items():
            detail = await agent.op("get_room_detail", room_id=room.room_id, connection=False)
            assert detail["channel_type"] == room.channel_type
            expected_group = (
                bootstrap.HACKATHON_GROUP if name in bootstrap.HACKATHON_ROOMS else "Acme"
            )
            assert detail["group_name"] == expected_group
        engineering = await agent.op(
            "get_room_detail", room_id=state.rooms["engineering"].room_id, connection=False
        )
        assert engineering["connected_user_names"] == ["tomas"]
        ops = await agent.op(
            "get_room_detail", room_id=state.rooms["splitbrain-ops"].room_id, connection=False
        )
        assert set(bootstrap.AGENT_NAMES) <= set(ops["agent_names"])
        assert {role["name"]: role["exclusive"] for role in ops["roles"]} == {
            "arbiter": True,
            "verifier": False,
        }

        ready = asyncio.Event()
        stop = asyncio.Event()

        async def handler(frame: SwitchFrame) -> None:
            if isinstance(frame, ConnectionStateFrame):
                ready.set()

        stream_task = asyncio.create_task(agent.run(handler, stop=stop))
        await asyncio.wait_for(ready.wait(), timeout=20.0)
        try:
            context = await agent.op(
                "connect_to_room", room_id=state.rooms["splitbrain-ops"].room_id
            )
        finally:
            stop.set()
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass

        links = [item for item in context["linked_rooms"] if item["label"] == "watches"]
        assert len(links) == 4
        assert any(item["name"] == "Acme roadmap" for item in context["references"])
        assert any(item["name"] == "How Splitbrain works" for item in context["documents"])
        roles = {item["name"]: item for item in context["roles"]}
        assert roles["arbiter"]["exclusive"] is True
        assert roles["verifier"]["exclusive"] is False
        assert "# Arbiter" in roles["arbiter"]["instructions_preview"]
    finally:
        await agent.aclose()

    gateway = GatewayAdmin(
        settings.api_base_url,
        settings.gateway_admin_email,
        settings.gateway_admin_password,
    )
    try:
        await gateway.login()
        bridges = await gateway.bridges()
        assert any(
            bridge.is_default and bridge.agent_greetings_enabled is False for bridge in bridges
        )
    finally:
        await gateway.aclose()

    password = state.mattermost.password
    team = settings.values.get("MATTERMOST_TEAM_NAME", "switch")
    for username, expected, forbidden, expected_type in (
        ("maria", "sales", "engineering", "O"),
        ("tomas", "engineering", "sales", "P"),
    ):
        user = await MattermostUser.login(settings.mattermost_url, username, password, team)
        try:
            channels = {channel.name: channel.type for channel in await user.channels()}
            assert expected in channels
            assert channels[expected] == expected_type
            assert forbidden not in channels
        finally:
            await user.aclose()
