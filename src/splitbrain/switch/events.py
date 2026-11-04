"""Pydantic v2 models for Switch agent protocol frames."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .sse import SSEFrame

logger = logging.getLogger(__name__)

DOMAIN_KINDS = frozenset(
    {
        "message",
        "command",
        "room_join",
        "task_delegate",
        "task_accept",
        "task_update",
        "task_finalise",
        "task_cancel",
    }
)


class GapPayload(BaseModel):
    """A buffered gap, attached to the next event the client surfaces."""

    model_config = ConfigDict(extra="allow")

    from_sequence: StrictInt | None = None
    resumed_at: StrictInt | None = None
    rooms: list[str] = Field(default_factory=list)
    reason: str = ""


class SwitchFrame(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str
    sequence: StrictInt | None = None
    gap: GapPayload | None = None


class ServerDeclaration(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: str | None = None
    contracts: dict[str, Any] = Field(default_factory=dict)


class ConnectionStateFrame(SwitchFrame):
    kind: Literal["connection_state"] = "connection_state"

    connection_id: str = ""
    agent_id: str = ""
    generation: StrictInt | None = None
    scope: str = ""
    filter: str = ""
    spawn_capable: bool = False
    rooms: list[str] = Field(default_factory=list)
    cursor: StrictInt = 0
    position: dict[str, Any] = Field(default_factory=dict)
    protocol: StrictInt | None = None
    heartbeat_interval_seconds: float = 2.0
    server: ServerDeclaration = Field(default_factory=ServerDeclaration)
    client: dict[str, Any] = Field(default_factory=dict)


class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    addressed: bool = False
    sender: str = ""
    sender_name: str = ""
    sender_kind: str | None = None
    on_behalf_of: str | None = None
    message_id: str = ""
    body: str = ""
    timestamp: StrictInt = 0
    thread_id: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class MessageFrame(SwitchFrame):
    kind: Literal["message"] = "message"

    room_id: str = ""
    bridge_id: str | None = None
    channel_type: str | None = None
    payload: MessagePayload = Field(default_factory=MessagePayload)
    sequence: StrictInt


class CommandPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    user_id: str = ""
    user_name: str = ""
    thread_id: str | None = None


class CommandFrame(SwitchFrame):
    kind: Literal["command"] = "command"

    room_id: str = ""
    payload: CommandPayload = Field(default_factory=CommandPayload)


class RoomJoinPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    member: str = ""
    member_name: str = ""
    timestamp: StrictInt = 0
    listening: bool = False


class RoomJoinFrame(SwitchFrame):
    kind: Literal["room_join"] = "room_join"

    room_id: str = ""
    payload: RoomJoinPayload = Field(default_factory=RoomJoinPayload)
    sequence: StrictInt


class SubscriptionChangedFrame(SwitchFrame):
    kind: Literal["subscription_changed"] = "subscription_changed"

    rooms: list[str] = Field(default_factory=list)
    reason: str = ""


class GapFrame(SwitchFrame):
    kind: Literal["gap"] = "gap"

    from_sequence: StrictInt | None = None
    resumed_at: StrictInt | None = None
    rooms: list[str] = Field(default_factory=list)
    reason: str = ""


class EvictedFrame(SwitchFrame):
    kind: Literal["evicted"] = "evicted"

    code: str = ""
    reason: str = ""
    room_id: str | None = None


class RoomReleasedFrame(SwitchFrame):
    kind: Literal["room_released"] = "room_released"

    room_id: str = ""
    session_id: str | None = None


class GenericFrame(SwitchFrame):
    data: dict[str, Any] = Field(default_factory=dict)
    raw: str = ""


_MODELS: dict[str, type[SwitchFrame]] = {
    "connection_state": ConnectionStateFrame,
    "message": MessageFrame,
    "command": CommandFrame,
    "room_join": RoomJoinFrame,
    "subscription_changed": SubscriptionChangedFrame,
    "gap": GapFrame,
    "evicted": EvictedFrame,
    "room_released": RoomReleasedFrame,
}


def parse_frame(frame: SSEFrame) -> SwitchFrame:
    """Turn one SSE frame into a model; unknown kinds become a logged generic frame."""
    try:
        data = json.loads(frame.data) if frame.data.strip() else {}
    except json.JSONDecodeError as exc:
        logger.warning("Malformed SSE data (%s); keeping it as a generic frame", exc)
        return GenericFrame(kind=frame.event or "unknown", raw=frame.data)
    if not isinstance(data, dict):
        logger.warning("SSE data was not an object; keeping it as a generic frame")
        return GenericFrame(kind=frame.event or "unknown", raw=frame.data)

    kind = frame.event or str(data.get("type") or "unknown")
    payload = dict(data)
    payload["kind"] = kind
    if "sequence" not in payload and kind in DOMAIN_KINDS and frame.id is not None:
        try:
            payload["sequence"] = int(frame.id)
        except ValueError:
            logger.warning("Ignoring non-numeric SSE id %r for %s", frame.id, kind)

    model = _MODELS.get(kind)
    if model is None:
        logger.warning("Unknown Switch frame kind %r; keeping it as a generic frame", kind)
        return GenericFrame(kind=kind, data=data, raw=frame.data)
    return model.model_validate(payload)
