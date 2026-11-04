"""Room discovery and claiming for agents that are not members of every room.

A `scope=all&filter=all` stream starts with an empty covered set: a room is
only covered after `connect_to_room` claims it (SWITCH_NOTES, M1/M4). The
Sentinel already does this itself; the Arbiter and Verifier share this helper.
"""

from __future__ import annotations

import logging
from typing import Any

from ..switch.client import SwitchAgent
from ..switch.events import (
    ConnectionStateFrame,
    RoomJoinFrame,
    SubscriptionChangedFrame,
)

logger = logging.getLogger(__name__)

OPS_ROOM = "splitbrain-ops"


class RoomCoverage:
    def __init__(self, agent: SwitchAgent, ops_room_id: str, *, own_name: str) -> None:
        self.agent = agent
        self.ops_room_id = ops_room_id
        self.own_name = own_name
        # Seed only the room we know we are a member of; refresh() adds the rest.
        self.rooms: dict[str, str] = {ops_room_id: OPS_ROOM}
        self.claimed: set[str] = set()
        self.covered: set[str] = set()
        self.connected = False

    async def refresh(self) -> None:
        result = await self.agent.op("list_rooms", connection=False)
        entries: Any = result if isinstance(result, list) else result.get("rooms", [])
        for item in entries:
            if not isinstance(item, dict):
                continue
            room_id = str(item.get("room_id") or "")
            name = str(item.get("name") or "")
            if room_id and name:
                self.rooms[room_id] = name

    async def claim(self, room_id: str) -> None:
        if not room_id or room_id in self.claimed:
            return
        # Mark before awaiting: connect_to_room itself emits subscription_changed.
        self.claimed.add(room_id)
        name = self.rooms.get(room_id, room_id[:8])
        try:
            async with self.agent.act_in(room_id):
                pass
            self.covered.add(room_id)
            logger.info("Claimed #%s for %s's event stream", name, self.own_name)
        except Exception:
            self.claimed.discard(room_id)
            logger.exception("Could not claim #%s; events there may be missed", name)

    async def on_connection_state(self, frame: ConnectionStateFrame) -> None:
        self.connected = True
        await self.refresh()
        for room_id, name in list(self.rooms.items()):
            # Claim ops and every conflict room we were added to; team rooms and
            # the bridged Mattermost defaults are not ours to connect to.
            if name == OPS_ROOM or name.startswith("conflict-"):
                await self.claim(room_id)
        for room_id in frame.rooms:
            self.covered.add(room_id)
            await self.claim(room_id)

    async def on_subscription(self, frame: SubscriptionChangedFrame) -> None:
        for room_id in frame.rooms:
            self.covered.add(room_id)
        if any(room_id not in self.rooms for room_id in frame.rooms):
            await self.refresh()
        for room_id in frame.rooms:
            await self.claim(room_id)

    async def on_room_join(self, frame: RoomJoinFrame) -> None:
        member = frame.payload.member_name or ""
        if member.casefold() != self.own_name.casefold():
            return
        await self.refresh()
        await self.claim(frame.room_id)

    async def ensure_known(self, room_id: str) -> None:
        if room_id in self.rooms:
            return
        await self.refresh()
        await self.claim(room_id)

    def name(self, room_id: str) -> str:
        return self.rooms.get(room_id, room_id[:8])
