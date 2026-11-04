"""M7: every demo scenario replays offline from committed cassettes, no API key.

Feeds each scenario through the real Sentinel pipeline (same Extractor,
Classifier, matcher and threshold as `splitbrain eval`) using only cassettes.
Near-misses must reach nobody; the three conflict scenarios must each produce
exactly one candidate. A missing extraction or classification cassette raises
ReplayMiss, so these tests are the keyless-demo guard.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from splitbrain import seed
from splitbrain.agents.sentinel import Sentinel
from splitbrain.config import LLMSettings
from splitbrain.core.models import Message
from splitbrain.core.store import ClaimStore
from splitbrain.llm.cassette import CassetteStore, ReplayMiss, extract_key
from splitbrain.llm.client import LLMClient

ROOT = Path(__file__).resolve().parents[1]
CONFLICT_SCENARIOS = ("sso", "refunds", "hackathon")
ALL_SCENARIOS = (*CONFLICT_SCENARIOS, "near-misses")


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


@pytest.mark.parametrize("name", ALL_SCENARIOS)
async def test_seed_scenarios_replay_without_an_api_key(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "")
    settings = LLMSettings.load(mode="replay")
    assert settings.api_key == ""
    cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode=settings.mode)
    llm = LLMClient(settings, cassettes)
    sink = Sink()
    # One fresh store per scenario: cross-scenario active claims are not part of
    # a demo run (the demo starts from a wiped stack every time).
    sentinel = Sentinel(
        agent=sink,  # type: ignore[arg-type]
        llm=llm,
        store=ClaimStore(":memory:"),
        state=seed.synthetic_state(),
        batch_window_s=0.0,
    )
    await sentinel.start()
    try:
        await sentinel.analyze_messages(_messages(name))
        expected = 0 if name == "near-misses" else 1
        assert sentinel.candidates_sent == expected, f"{name}: wrong candidate count"
        assert len(sink.sent) == expected
        assert all(room_id == "r-splitbrain-ops" for room_id, _ in sink.sent)
        assert all(body.splitlines()[-1].startswith("sb:candidate ") for _, body in sink.sent)
    finally:
        await sentinel.aclose()


def test_every_seed_message_has_an_extraction_cassette() -> None:
    settings = LLMSettings.load(mode="replay")
    cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode="replay")
    for name in ALL_SCENARIOS:
        for message in _messages(name):
            key = extract_key(message.text)
            try:
                cassettes.read("extract", key, f"{name}: {message.text[:40]}")
            except ReplayMiss as exc:
                pytest.fail(f"missing extraction cassette for {name}: {exc}")
