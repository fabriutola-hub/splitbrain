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


async def test_auto_decide_fails_loudly_in_m4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed, "load_scenario", lambda _settings, _name: None)
    with pytest.raises(SplitbrainError, match="M5"):
        await seed.run(settings(), "sso", auto_decide=True)
