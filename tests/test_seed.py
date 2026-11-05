"""Seed scenarios: format, validation and the near-miss contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from splitbrain import seed
from splitbrain.config import SplitbrainError
from splitbrain.core.models import Claim, ClaimKind
from splitbrain.core.store import ClaimStore

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


def test_sso_followup_scenario_matches_spec_format() -> None:
    scenario = seed.load_scenario(settings(), "sso-followup")
    assert scenario.name == "sso-followup"
    assert [m.room for m in scenario.messages] == ["support", "finance"]
    assert [m.person for m in scenario.messages] == ["lucia", "pablo"]
    assert scenario.decision is None


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
    with pytest.raises(
        SplitbrainError, match="Available: hackathon, near-misses, refunds, sso, sso-followup"
    ):
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


def _state_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    paths = SimpleNamespace(root=tmp_path, state_dir=tmp_path / ".splitbrain")
    (tmp_path / ".splitbrain").mkdir()
    (tmp_path / ".splitbrain" / "state.json").write_text(
        '{"rooms": {"splitbrain-ops": {"room_id": "ops-1"}}}', encoding="utf-8"
    )
    monkeypatch.setattr(seed, "SEED_STATE_FILE", "seeded-it.json")
    return SimpleNamespace(paths=paths)


async def test_guard_blocks_only_a_repeat_of_the_same_scenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _state_settings(tmp_path, monkeypatch)
    sso = seed.load_scenario(settings(), "sso")
    near = seed.load_scenario(settings(), "near-misses")

    await seed.check_stale_claims(config, sso)  # nothing seeded yet
    seed.mark_seeded(config, "sso")
    assert seed.read_seeded(config) == ["sso"]
    await seed.check_stale_claims(config, near)  # a different scenario is allowed

    with pytest.raises(SplitbrainError) as error:
        await seed.check_stale_claims(config, sso)
    message = str(error.value)
    assert "'sso'" in message
    assert "lists 'sso'" in message
    assert "already seeded on this stack" in message


async def test_sso_followup_guard_requires_an_active_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _state_settings(tmp_path, monkeypatch)
    followup = seed.load_scenario(settings(), "sso-followup")
    seed.mark_seeded(config, "sso")

    # Without an active DECISION claim, sso-followup is refused with clear guidance.
    with pytest.raises(SplitbrainError) as error:
        await seed.check_stale_claims(config, followup)
    assert "run `uv run splitbrain demo --auto-decide` first" in str(error.value)

    store = ClaimStore(tmp_path / ".splitbrain" / "sentinel.db")
    try:
        await store.add_claim(
            Claim(
                id="clm_dec",
                room_id="r-conflict",
                room_name="conflict-sb-0001-sso",
                message_id="decision:sb-0001",
                author="maria",
                text="SSO beta for Acme on December 15, GA in Q1.",
                kind=ClaimKind.DECISION,
                subject="SSO",
                subject_key="sso",
                scope="Acme",
                scope_key="acme",
                value="SSO beta for Acme on December 15, GA in Q1.",
            )
        )
    finally:
        await store.close()

    # Once a decision is recorded, sso-followup is allowed after sso.
    await seed.check_stale_claims(config, followup)


def test_seeded_state_is_invalidated_by_a_new_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _state_settings(tmp_path, monkeypatch)
    seed.mark_seeded(config, "sso")
    assert seed.read_seeded(config) == ["sso"]
    (tmp_path / ".splitbrain" / "state.json").write_text(
        '{"rooms": {"splitbrain-ops": {"room_id": "ops-2"}}}', encoding="utf-8"
    )
    assert seed.read_seeded(config) == []


def test_sso_noise_does_not_mention_refunds() -> None:
    scenario = seed.load_scenario(settings(), "sso")
    noise = next(m.text for m in scenario.messages if m.room == "support")
    assert "refund" not in noise.casefold()
    assert "support desk" in noise
