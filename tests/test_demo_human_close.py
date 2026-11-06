"""The human-decision demo must wait for the Arbiter's closing line."""

from __future__ import annotations

from typing import Any

import pytest

from splitbrain import demo
from splitbrain.config import SplitbrainError
from splitbrain.core.models import Decision
from splitbrain.core.packets import encode
from splitbrain.core.protocol import CorrectedPacket, DecidedPacket

OPS_ROOM = "r-ops"
CONFLICT_ROOM = "conflict-sb-0001-refunds"
CONFLICT_ROOM_ID = "r-conflict"
CLOSING_LINE = (
    "Corrections posted in #support, #finance; "
    '"Customer commitments" updated for Acme in #splitbrain-ops; '
    "follow-up assigned to @Lucía Pérez: retire the $500 macro (due Nov 6)."
)


def _decided_packet() -> DecidedPacket:
    return DecidedPacket(
        candidate_id="sb-0001",
        decision=Decision(
            candidate_id="sb-0001",
            room_id=CONFLICT_ROOM_ID,
            text="Refunds above $250 need manager approval.",
            proposed_by="lucia",
            confirmed_by="pablo",
            decided_at="2026-11-06T07:18:23+00:00",
        ),
        conflict_room=CONFLICT_ROOM_ID,
        conflict_room_name=CONFLICT_ROOM,
        origins=[],
        subject="refunds",
        authors=["lucia", "pablo"],
    )


def _corrected_packet() -> CorrectedPacket:
    return CorrectedPacket(
        candidate_id="sb-0001",
        conflict_room=CONFLICT_ROOM_ID,
        conflict_room_name=CONFLICT_ROOM,
        rooms=["support", "finance"],
    )


class FakeGroup:
    def check(self) -> None:
        pass


class FakeObserver:
    def __init__(self, *, closing_after: int | None) -> None:
        self.closing_after = closing_after
        self.conflict_reads = 0
        self.closing_seen = False
        self.events: list[str] = []

    async def op(self, name: str, /, **kwargs: Any) -> Any:
        if name == "list_all_rooms":
            return [{"name": CONFLICT_ROOM, "room_id": CONFLICT_ROOM_ID}]
        if name == "read_context":
            room_id = kwargs.get("room_id")
            if room_id == OPS_ROOM:
                self.events.append("ops")
                return {
                    "threads": [
                        {
                            "root": {
                                "body": "Decision recorded.\n"
                                + encode("decided", _decided_packet())
                            },
                            "replies": [],
                        },
                        {
                            "root": {
                                "body": "Corrections.\n" + encode("corrected", _corrected_packet())
                            },
                            "replies": [],
                        },
                    ]
                }
            if room_id == CONFLICT_ROOM_ID:
                self.conflict_reads += 1
                if self.closing_after is not None and self.conflict_reads >= self.closing_after:
                    self.closing_seen = True
                    self.events.append("closing")
                    return {"threads": [{"root": {"body": CLOSING_LINE}, "replies": []}]}
                return {"threads": [{"root": {"body": "brief"}, "replies": []}]}
        raise AssertionError(f"unexpected op {name!r} {kwargs!r}")


async def test_human_close_waits_for_the_arbiter_closing_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo, "POLL_S", 0.01)
    observer = FakeObserver(closing_after=2)
    decision, corrections = await demo._wait_for_human_close(
        FakeGroup(),
        observer,
        OPS_ROOM,
        CONFLICT_ROOM,  # type: ignore[arg-type]
    )
    assert observer.closing_seen is True
    assert observer.conflict_reads >= 2
    assert observer.events.index("ops") < observer.events.index("closing")
    assert decision is not None
    assert decision["text"] == "Refunds above $250 need manager approval."
    assert corrections == ["support", "finance"]


async def test_human_close_fails_loudly_when_the_closing_line_never_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo, "POLL_S", 0.01)
    monkeypatch.setattr(demo.seed, "CORRECTIONS_TIMEOUT_S", 0.05)
    observer = FakeObserver(closing_after=None)
    with pytest.raises(SplitbrainError, match="Corrections posted.*conflict-sb-0001-refunds"):
        await demo._wait_for_human_close(
            FakeGroup(),
            observer,
            OPS_ROOM,
            CONFLICT_ROOM,  # type: ignore[arg-type]
        )
