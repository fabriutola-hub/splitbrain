"""Protocol integration: the real Switch stack (compose project `splitbrain`).

Everything created here is temporary and prefixed `it-`. Reserved demo names
(splitbrain-*, maria, tomas, lucia, pablo, fabrizio) are never touched.
"""

from __future__ import annotations

import asyncio
import secrets
import time
import uuid

import pytest

from splitbrain.config import Settings
from splitbrain.switch.client import SwitchAgent
from splitbrain.switch.events import (
    ConnectionStateFrame,
    MessageFrame,
    SubscriptionChangedFrame,
    SwitchFrame,
)
from splitbrain.switch.gateway import GatewayAdmin
from splitbrain.switch.mattermost import MattermostAdmin, MattermostError, MattermostUser

pytestmark = pytest.mark.integration


async def _wait_for_channel(user: MattermostUser, room_name: str, timeout: float = 30.0) -> str:
    deadline = time.monotonic() + timeout
    while True:
        try:
            return await user.channel_for_room(room_name)
        except MattermostError as exc:
            if exc.status != 404:
                raise
        if time.monotonic() >= deadline:
            raise AssertionError(f"Mattermost channel for {room_name!r} never appeared")
        await asyncio.sleep(0.5)


async def _wait_for_thread_reply(
    user: MattermostUser, post_id: str, reply_body: str, timeout: float = 30.0
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        posts = await user.thread(post_id)
        if any(post.message == reply_body for post in posts):
            return
        if time.monotonic() >= deadline:
            raise AssertionError(f"threaded reply never appeared in Mattermost thread {post_id!r}")
        await asyncio.sleep(0.5)


async def test_switch_unaddressed_message_and_threaded_reply() -> None:
    settings = Settings.load()
    suffix = uuid.uuid4().hex[:8]
    agent_name = f"it-agent-{suffix}"
    username = f"it-user-{suffix}"
    room_name = f"it-room-{suffix}"
    password = secrets.token_hex(12)
    body = f"probe {suffix}: SSO goes live on December 1."
    reply_body = f"threaded reply {suffix}"

    admin = MattermostAdmin(
        settings.mattermost_url,
        settings.values["MATTERMOST_ADMIN_USER"],
        settings.values["MATTERMOST_ADMIN_PASSWORD"],
        settings.values.get("MATTERMOST_TEAM_NAME", "switch"),
    )
    user: MattermostUser | None = None
    gateway = GatewayAdmin(
        settings.api_base_url,
        settings.gateway_admin_email,
        settings.gateway_admin_password,
    )
    agent: SwitchAgent | None = None
    run_task: asyncio.Task[None] | None = None

    try:
        await admin.login()
        user = await admin.ensure_user(username, password)
        credentials = await SwitchAgent.register(
            settings.api_base_url,
            settings.values["AGENT_REGISTRATION_TOKEN"],
            agent_name,
            "protocol integration probe",
        )
        await gateway.login()
        bridges = await gateway.bridges()
        assert any(bridge.display_name == "Mattermost" for bridge in bridges)
        await gateway.open_addressing(credentials.agent_id)

        agent = SwitchAgent(settings.api_base_url, credentials.agent_id, credentials.api_key)
        state_ready = asyncio.Event()
        message_ready = asyncio.Event()
        rooms_seen: list[list[str]] = []
        received: dict[str, MessageFrame] = {}
        frames_seen: list[str] = []

        async def handler(event: SwitchFrame) -> None:
            detail = getattr(getattr(event, "payload", None), "body", "")[:60]
            frames_seen.append(f"{event.kind}:{detail}")
            if isinstance(event, ConnectionStateFrame):
                state_ready.set()
            elif isinstance(event, SubscriptionChangedFrame):
                rooms_seen.append(event.rooms)
            elif isinstance(event, MessageFrame) and event.payload.body == body:
                received["message"] = event
                message_ready.set()

        run_task = asyncio.create_task(agent.run(handler))
        await asyncio.wait_for(state_ready.wait(), timeout=20.0)

        room = await agent.op(
            "create_room",
            name=room_name,
            description="protocol integration probe",
            agent_names=[agent_name],
            user_names=[username],
            channel_type="channel_public",
        )
        room_id = str(room["id"])
        # A scope=all stream covers the room once this connection claims it.
        await agent.op("connect_to_room", room_id=room_id)

        deadline = time.monotonic() + 25.0
        while not any(room_id in rooms for rooms in rooms_seen):
            if time.monotonic() >= deadline:
                raise AssertionError("the agent stream never covered the new room")
            await asyncio.sleep(0.2)

        channel_id = await _wait_for_channel(user, room_name)
        # The bridge needs a moment to subscribe to the freshly created channel.
        await asyncio.sleep(1.0)
        post_id = await user.post(channel_id, body)
        try:
            await asyncio.wait_for(message_ready.wait(), timeout=25.0)
        except TimeoutError as exc:
            raise AssertionError(
                f"unaddressed message never arrived; frames seen: {frames_seen[-10:]}"
            ) from exc

        message = received["message"]
        assert message.payload.addressed is False
        assert message.payload.sender_name == username
        assert message.payload.message_id
        assert isinstance(message.sequence, int) and message.sequence > 0
        assert agent.server_version == "0.31.0"

        await agent.post(room_id, reply_body, thread_id=message.payload.message_id)
        await _wait_for_thread_reply(user, post_id, reply_body)
    finally:
        if run_task is not None:
            run_task.cancel()
            try:
                await run_task
            except asyncio.CancelledError:
                pass
        if agent is not None:
            await agent.aclose()
        if user is not None:
            await user.aclose()
        await admin.aclose()
        await gateway.aclose()
