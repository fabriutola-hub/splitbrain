"""Every demo scenario replays offline from committed cassettes, no API key.

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

from splitbrain import recording, seed
from splitbrain.agents.sentinel import Sentinel
from splitbrain.config import LLMSettings
from splitbrain.core.models import ClaimStatus, Message
from splitbrain.core.store import ClaimStore
from splitbrain.llm.cassette import CassetteStore, ReplayMiss, extract_key
from splitbrain.llm.client import LLMClient

ROOT = Path(__file__).resolve().parents[1]
CONFLICT_SCENARIOS = ("sso", "refunds", "hackathon")
ALL_SCENARIOS = (*CONFLICT_SCENARIOS, "near-misses")
SCENARIOS_WITH_CASSETTES = (*ALL_SCENARIOS, "sso-followup")


class Sink:
    """A SwitchAgent stand-in that records targeted posts and room replies."""

    agent_id = "sink"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.replies: list[tuple[str, str, str | None]] = []

    async def op(self, name: str, /, **kwargs: Any) -> Any:
        if name == "connect_to_room":
            return {"documents": [{"id": "doc-1"}]}
        if name == "load_internal_documents":
            return [
                {
                    "id": "doc-1",
                    "content": "Status: DECIDED\nProposed by: @maria\nConfirmed by: @tomas\n",
                }
            ]
        return []

    async def post(
        self, room_id: str, body: str, *, thread_id: str | None = None
    ) -> dict[str, str]:
        self.replies.append((room_id, body, thread_id))
        return {"event_id": "sw_remind"}

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
    for name in SCENARIOS_WITH_CASSETTES:
        for message in _messages(name):
            key = extract_key(message.text)
            try:
                cassettes.read("extract", key, f"{name}: {message.text[:40]}")
            except ReplayMiss as exc:
                pytest.fail(f"missing extraction cassette for {name}: {exc}")


async def test_sso_followup_replays_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "")
    settings = LLMSettings.load(mode="replay")
    assert settings.api_key == ""
    cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode=settings.mode)
    llm = LLMClient(settings, cassettes)
    sink = Sink()
    store = ClaimStore(":memory:")
    sentinel = Sentinel(
        agent=sink,  # type: ignore[arg-type]
        llm=llm,
        store=store,
        state=seed.synthetic_state(),
        batch_window_s=0.0,
    )
    await sentinel.start()
    try:
        await store.add_claim(recording.sso_decision_claim(ROOT))
        await sentinel.analyze_messages(_messages("sso-followup"))
        assert sentinel.candidates_sent == 0
        assert len(sentinel.reminded_messages) == 1
        assert len(sink.replies) == 1
        room_id, body, reply_to = sink.replies[0]
        assert room_id == "support"
        assert reply_to == "sso-followup-0"
        assert body.startswith("Heads-up: this was already decided.")
        assert "María Gómez and Tomás Rivera agreed:" in body
        assert len(sink.sent) == 1
        ops_room, ops_body = sink.sent[0]
        assert ops_room == "r-splitbrain-ops"
        assert ops_body.splitlines()[-1].startswith("sb:reminded ")
        active = await store.active_claims()
        assert [c.author for c in active if c.author == "lucia"] == []
        assert [c.author for c in active if c.author == "pablo"] == ["pablo"]
        rows = store._connection.execute("SELECT status, payload FROM claims").fetchall()
        assert any(
            status == ClaimStatus.SUPERSEDED and '"lucia"' in payload for status, payload in rows
        )
    finally:
        await sentinel.aclose()
