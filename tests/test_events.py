"""Unit tests for Switch frame models."""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from splitbrain.switch.events import (
    ConnectionStateFrame,
    EvictedFrame,
    GapFrame,
    GenericFrame,
    MessageFrame,
    RoomJoinFrame,
    RoomReleasedFrame,
    SubscriptionChangedFrame,
    parse_frame,
)
from splitbrain.switch.sse import SSEFrame

BIG_SEQUENCE = 9007194959773697


def sse(event: str, data: dict[str, object], *, frame_id: str | None = None) -> SSEFrame:
    return SSEFrame(id=frame_id, event=event, data=json.dumps(data))


def test_connection_state_carries_the_server_version() -> None:
    frame = parse_frame(
        sse(
            "connection_state",
            {
                "connection_id": "conn-1",
                "agent_id": "agent-1",
                "scope": "all",
                "filter": "all",
                "rooms": [],
                "cursor": BIG_SEQUENCE,
                "protocol": 9,
                "heartbeat_interval_seconds": 2.0,
                "server": {"version": "0.31.0", "contracts": {"agent-protocol": {"speaks": 1}}},
            },
        )
    )
    assert isinstance(frame, ConnectionStateFrame)
    assert frame.server.version == "0.31.0"
    assert frame.cursor == BIG_SEQUENCE
    assert isinstance(frame.cursor, int)
    assert frame.heartbeat_interval_seconds == 2.0


def test_message_sequence_is_an_exact_int() -> None:
    frame = parse_frame(
        sse(
            "message",
            {
                "type": "message",
                "room_id": "room-1",
                "channel_type": "channel_public",
                "payload": {
                    "addressed": False,
                    "sender_name": "maria",
                    "message_id": "sw_1",
                    "body": "SSO on Dec 1",
                    "timestamp": BIG_SEQUENCE,
                    "thread_id": None,
                },
                "sequence": BIG_SEQUENCE,
            },
            frame_id=str(BIG_SEQUENCE),
        )
    )
    assert isinstance(frame, MessageFrame)
    assert isinstance(frame.sequence, int)
    assert frame.sequence == BIG_SEQUENCE
    assert frame.payload.timestamp == BIG_SEQUENCE
    assert frame.payload.addressed is False


def test_float_sequence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_frame(sse("message", {"payload": {"body": "x"}, "sequence": float(BIG_SEQUENCE)}))


def test_domain_sequence_falls_back_to_the_sse_id() -> None:
    frame = parse_frame(
        sse("room_join", {"payload": {"member_name": "tomas", "listening": False}}, frame_id="99")
    )
    assert isinstance(frame, RoomJoinFrame)
    assert frame.sequence == 99
    assert isinstance(frame.sequence, int)


def test_control_frames() -> None:
    changed = parse_frame(sse("subscription_changed", {"rooms": ["a"], "reason": "x"}))
    gap = parse_frame(sse("gap", {"from_sequence": 1, "resumed_at": 2, "reason": "restart"}))
    evicted = parse_frame(sse("evicted", {"code": "taken_over", "reason": "other stream"}))
    released = parse_frame(sse("room_released", {"room_id": "r1", "session_id": None}))
    assert isinstance(changed, SubscriptionChangedFrame) and changed.rooms == ["a"]
    assert isinstance(gap, GapFrame) and gap.resumed_at == 2
    assert isinstance(evicted, EvictedFrame) and evicted.code == "taken_over"
    assert isinstance(released, RoomReleasedFrame) and released.session_id is None


def test_unknown_kind_is_generic_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        frame = parse_frame(sse("future_event", {"foo": "bar"}))
    assert isinstance(frame, GenericFrame)
    assert frame.kind == "future_event"
    assert frame.data == {"foo": "bar"}
    assert "Unknown Switch frame kind" in caplog.text


def test_malformed_json_is_generic_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        frame = parse_frame(SSEFrame(id=None, event="message", data="{not json"))
    assert isinstance(frame, GenericFrame)
    assert frame.kind == "message"
    assert "Malformed SSE data" in caplog.text


def test_event_name_wins_over_a_missing_type() -> None:
    frame = parse_frame(sse("connection_state", {"agent_id": "a"}))
    assert isinstance(frame, ConnectionStateFrame)
    assert frame.agent_id == "a"
