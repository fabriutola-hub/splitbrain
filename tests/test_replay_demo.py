"""The M4 demo replays offline from committed cassettes, with no API key.

Feeds both seed scenarios through the real Sentinel pipeline (same Extractor,
Classifier, matcher and threshold as `splitbrain eval`) using only cassettes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from splitbrain import bootstrap, seed
from splitbrain.agents.sentinel import Sentinel
from splitbrain.config import LLMSettings
from splitbrain.core.models import Message
from splitbrain.core.store import ClaimStore
from splitbrain.llm.cassette import CassetteStore, ReplayMiss
from splitbrain.llm.client import LLMClient

ROOT = Path(__file__).resolve().parents[1]


class Sink:
    """A SwitchAgent stand-in that only records targeted posts."""

    agent_id = "sink"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def op(self, name: str, /, **kwargs: Any) -> list[Any]:
        return []

    @asynccontextmanager
    async def act_in(self, room_id: str):
        yield self

    async def targeted(self, room_id: str, body: str, **kwargs: Any) -> dict[str, str]:
        self.sent.append((room_id, body))
        return {"event_id": "sw_replay"}

    async def aclose(self) -> None:
        return None


def _state() -> bootstrap.BootstrapState:
    return bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(
                room_id=f"r-{name}",
                channel_type="channel_private" if name == "engineering" else "channel_public",
            )
            for name in (
                "sales",
                "engineering",
                "support",
                "finance",
                "splitbrain-ops",
            )
        }
    )


def _messages(name: str) -> list[Message]:
    scenario = seed.load_scenario(SimpleNamespace(paths=SimpleNamespace(root=ROOT)), name)
    return [
        Message(
            message_id=f"{name}-{index}",
            room_id=item.room,
            room_name=item.room,
            channel_type="channel_private" if item.room == "engineering" else "channel_public",
            author=item.person,
            text=item.text,
        )
        for index, item in enumerate(scenario.messages)
    ]


async def test_seed_scenarios_replay_without_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "")
    settings = LLMSettings.load(mode="replay")
    assert settings.api_key == ""
    cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode=settings.mode)
    llm = LLMClient(settings, cassettes)
    sink = Sink()
    sentinel = Sentinel(
        agent=sink,  # type: ignore[arg-type]
        llm=llm,
        store=ClaimStore(":memory:"),
        state=_state(),
        batch_window_s=0.0,
    )
    await sentinel.start()
    try:
        await sentinel.analyze_messages(_messages("sso"))
        assert sentinel.candidates_sent == 1
        await sentinel.analyze_messages(_messages("near-misses"))
        assert sentinel.candidates_sent == 1, "a near-miss produced a candidate"
        assert len(sink.sent) == 1
        assert all(room_id == "r-splitbrain-ops" for room_id, _ in sink.sent)
        assert sink.sent[0][1].splitlines()[-1].startswith("sb:candidate ")
    finally:
        await sentinel.aclose()


def test_every_seed_message_has_an_extraction_cassette() -> None:
    """A replay miss would break the no-key demo; catch it here."""
    settings = LLMSettings.load(mode="replay")
    cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode="replay")
    from splitbrain.llm.cassette import extract_key

    for name in ("sso", "near-misses"):
        for message in _messages(name):
            key = extract_key(message.text)
            try:
                cassettes.read("extract", key, f"{name}: {message.text[:40]}")
            except ReplayMiss as exc:
                pytest.fail(f"missing extraction cassette for {name}: {exc}")
