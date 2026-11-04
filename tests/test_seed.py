"""M4 seed scenarios: format, validation and the near-miss contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from splitbrain import seed
from splitbrain.config import SplitbrainError

ROOT = Path(__file__).resolve().parents[1]


def settings() -> SimpleNamespace:
    return SimpleNamespace(paths=SimpleNamespace(root=ROOT))


def test_sso_scenario_matches_spec_format() -> None:
    scenario = seed.load_scenario(settings(), "sso")
    assert scenario.name == "sso"
    assert len(scenario.messages) == 4
    assert [m.room for m in scenario.messages] == [
        "sales",
        "support",
        "engineering",
        "finance",
    ]
    assert {m.person for m in scenario.messages} <= set(scenario.people)
    assert scenario.decision is not None
    assert scenario.decision.propose["as"] == "maria"
    assert all(m.after_s >= 0 for m in scenario.messages)


def test_near_misses_are_five_to_seven_messages_in_distinct_rooms() -> None:
    scenario = seed.load_scenario(settings(), "near-misses")
    assert 5 <= len(scenario.messages) <= 7
    assert len({m.room for m in scenario.messages}) >= 4
    # Every message must be a plausible conflict: the prefilter has to see it.
    from splitbrain.core.models import Message
    from splitbrain.core.prefilter import prefilter

    for index, item in enumerate(scenario.messages):
        message = Message(
            message_id=f"m{index}",
            room_id=item.room,
            room_name=item.room,
            author=item.person,
            text=item.text,
        )
        assert prefilter(message).keep, f"prefilter drops near-miss {index}: {item.text}"


def test_unknown_scenario_lists_available_ones() -> None:
    with pytest.raises(SplitbrainError, match="Available: near-misses, sso"):
        seed.load_scenario(settings(), "does-not-exist")


def test_path_traversal_is_rejected() -> None:
    with pytest.raises(SplitbrainError, match="Invalid scenario name"):
        seed.load_scenario(settings(), "../../etc/passwd")


async def test_auto_decide_without_a_decision_block_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = seed.Scenario(
        name="sso",
        people={"maria": "Maria"},
        messages=[seed.SeedMessage(room="sales", **{"as": "maria"}, text="SSO on Dec 1")],
    )
    monkeypatch.setattr(seed, "load_scenario", lambda _settings, _name: scenario)
    with pytest.raises(SplitbrainError, match="no 'decision:' block"):
        await seed.run(settings(), "sso", auto_decide=True)


async def test_wait_for_says_what_it_expected() -> None:
    async def nothing() -> None:
        return None

    with pytest.raises(SplitbrainError) as error:
        await seed._wait_for("the consent question in #engineering thread sw_1", 0.01, nothing)
    assert "the consent question in #engineering thread sw_1" in str(error.value)
    assert "Timed out after" in str(error.value)
    assert "sentinel, arbiter, verifier" in str(error.value)


def test_conflict_room_names_are_filtered_from_both_registry_shapes() -> None:
    import asyncio

    class FakeAgent:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        async def op(self, name: str, /, **kwargs: object) -> object:
            return self.payload

    bare = [
        {"name": "sales", "room_id": "1"},
        {"name": "conflict-sb-0001-sso", "room_id": "2"},
    ]
    assert asyncio.run(seed._conflict_rooms(FakeAgent(bare))) == {"conflict-sb-0001-sso"}
    assert asyncio.run(seed._conflict_rooms(FakeAgent({"rooms": bare}))) == {"conflict-sb-0001-sso"}
