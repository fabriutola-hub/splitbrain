"""Recovery orchestration and crash checkpoints, without processes or a stack."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from decision_fakes import FakeSwitch
from test_decision_integrity import (
    arbiter_for,
    decided_arbiter,
    decision_frame,
    human,
    open_arbiter,
    propose,
    sentinel_for,
)

from splitbrain import bootstrap, cli, demo, demo_faults, recovery_demo, seed
from splitbrain.config import SplitbrainError
from splitbrain.core.decision_record import (
    PROGRESS_PREFIX,
    CorrectionJournal,
    load_correction_journal,
)


class FakeProcess:
    pid = 123

    def __init__(self, code: int | None = None) -> None:
        self.returncode = code

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        assert self.returncode is not None
        return self.returncode


def fake_group() -> demo.AgentGroup:
    return demo.AgentGroup(
        [
            demo.Child(name=name, proc=FakeProcess())  # type: ignore[arg-type]
            for name in ("arbiter", "arbiter-b", "sentinel", "verifier")
        ]
    )


@pytest.mark.parametrize("value", [None, "unrecognized-fault"])
async def test_sentinel_fault_is_disabled_without_the_exact_variable(
    value: str | None, tmp_path: Path, llm_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value is None:
        monkeypatch.delenv(demo_faults.ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(demo_faults.ENV_VAR, value)
    _, _, primary, packet = await decided_arbiter()
    agent = FakeSwitch("splitbrain-sentinel", primary.state)
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    monkeypatch.setattr(demo_faults.os, "_exit", lambda code: pytest.fail("unexpected crash"))
    try:
        await sentinel.on_frame(decision_frame(packet))
        _, journal = await load_correction_journal(agent, "r-conflict", "sb-0001")
        assert len(agent.posts) == 2
        assert journal.complete and journal.notified
    finally:
        await sentinel.aclose()


async def test_sentinel_crashes_only_after_the_first_receipt_is_persisted(
    tmp_path: Path, llm_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(demo_faults.ENV_VAR, demo_faults.SENTINEL_AFTER_FIRST)
    _, _, primary, packet = await decided_arbiter()
    agent = FakeSwitch("splitbrain-sentinel", primary.state)
    sentinel = sentinel_for(agent, llm_factory, tmp_path)

    def crash(code: int) -> None:
        content = next(
            item["content"]
            for item in agent.state.documents.values()
            if item["name"] == "SB-0001 correction progress"
        )
        saved = CorrectionJournal.model_validate_json(content.rpartition(PROGRESS_PREFIX)[2])
        assert [item.status for item in saved.threads] == ["posted", "pending"]
        assert saved.threads[0].message_id == agent.posts[0]["id"]
        assert len(agent.posts) == 1
        assert not agent.targeted_calls
        raise SystemExit(code)

    monkeypatch.setattr(demo_faults.os, "_exit", crash)
    try:
        with pytest.raises(SystemExit) as stopped:
            await sentinel.on_frame(decision_frame(packet))
        assert stopped.value.code == demo_faults.EXIT_CODE
        assert "sb-0001" not in sentinel.corrected
    finally:
        await sentinel.aclose()


async def test_failed_receipt_checkpoint_does_not_trigger_the_demo_crash(
    tmp_path: Path, llm_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(demo_faults.ENV_VAR, demo_faults.SENTINEL_AFTER_FIRST)
    _, _, primary, packet = await decided_arbiter()
    agent = FakeSwitch("splitbrain-sentinel", primary.state)
    agent.fail_checkpoint_after_post = True
    sentinel = sentinel_for(agent, llm_factory, tmp_path)
    monkeypatch.setattr(demo_faults.os, "_exit", lambda code: pytest.fail("receipt was not saved"))
    try:
        with pytest.raises(RuntimeError, match="checkpoint failed"):
            await sentinel.on_frame(decision_frame(packet))
        _, journal = await load_correction_journal(agent, "r-conflict", "sb-0001")
        assert [item.status for item in journal.threads] == ["pending", "pending"]
    finally:
        await sentinel.aclose()


@pytest.mark.parametrize(
    "argv",
    [
        ["demo", "--recovery"],
        ["demo", "--recovery", "--scenario", "refunds", "--auto-decide"],
        ["demo", "--recovery", "--scenario", "hackathon", "--auto-decide"],
    ],
)
def test_cli_rejects_invalid_recovery_flags_before_loading_the_stack(
    argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run = AsyncMock()
    monkeypatch.setattr(cli.demo, "run", run)
    assert cli.main(argv) == 1
    assert "--recovery requires --scenario sso and --auto-decide" in capsys.readouterr().err
    run.assert_not_awaited()


def test_cli_dispatches_recovery_and_preserves_other_sso_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = AsyncMock()
    monkeypatch.setattr(cli.demo, "run", run)
    assert cli.main(["demo", "--auto-decide", "--recovery", "--offline", "--followup"]) == 0
    run.assert_awaited_once_with(
        scenario="sso", auto_decide=True, offline=True, keep=False, followup=True, recovery=True
    )


def test_agent_health_only_allows_the_expected_crash_code() -> None:
    group = fake_group()
    sentinel = group.child("sentinel")
    sentinel.proc.returncode = demo_faults.EXIT_CODE
    with pytest.raises(SplitbrainError, match="exited early"):
        group.check()
    sentinel.expected_returncode = demo_faults.EXIT_CODE
    group.check()
    sentinel.proc.returncode = 1
    with pytest.raises(SplitbrainError, match="code 1"):
        group.check()


async def test_spawn_scopes_the_fault_to_the_sentinel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environments: list[dict[str, str]] = []

    async def spawn(*args: Any, **kwargs: Any) -> Any:
        environments.append(kwargs["env"])
        stream = asyncio.StreamReader()
        stream.feed_eof()
        return SimpleNamespace(stdout=stream, pid=1)

    monkeypatch.setattr(demo.asyncio, "create_subprocess_exec", spawn)
    env = {demo_faults.ENV_VAR: demo_faults.SENTINEL_AFTER_FIRST}
    for name in ("sentinel", "arbiter-b"):
        child = await demo._start_child(tmp_path, env, name, ("run", name))
        await child.reader
    assert environments[0][demo_faults.ENV_VAR] == demo_faults.SENTINEL_AFTER_FIRST
    assert demo_faults.ENV_VAR not in environments[1]
    assert demo_faults.ENV_VAR in env


async def test_recovery_wait_reports_expected_and_last_observed_state() -> None:
    with pytest.raises(SplitbrainError, match="expected arbiter-b.*observed.*primary"):
        await recovery_demo.wait_for_observation(
            demo.AgentGroup([]),
            "arbiter-b",
            AsyncMock(return_value="primary"),
            lambda observed: observed == "arbiter-b",
            timeout_s=0,
        )


async def test_recovery_wait_keeps_polling_until_switch_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recovery_demo, "POLL_S", 0)
    poll = AsyncMock(side_effect=["primary", "standby"])
    result = await recovery_demo.wait_for_observation(
        demo.AgentGroup([]), "standby", poll, lambda observed: observed == "standby"
    )
    assert result == "standby" and poll.await_count == 2


async def test_seed_waits_for_takeover_before_posting_the_same_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[1]
    settings = SimpleNamespace(paths=SimpleNamespace(root=root), api_base_url="http://unused")
    scenario = seed.load_scenario(settings, "sso")
    state = bootstrap.BootstrapState(
        agents={
            "splitbrain-sentinel": bootstrap.AgentState(agent_id="fake", api_key="unit-test-key")
        }
    )
    events: list[str] = []

    class User:
        async def post(self, channel: str, text: str) -> str:
            events.append(text)
            return "mm-post"

    class Hooks:
        async def before_confirm(self, room: str) -> None:
            assert events == [scenario.decision.propose["text"]]
            events.append("takeover verified")

        async def after_confirm(self, room: str) -> None:
            assert events[-1] == scenario.decision.confirm["text"]
            events.append("restart and duplicate verified")

    user = User()
    monkeypatch.setattr(seed, "SwitchAgent", lambda *args: SimpleNamespace(aclose=AsyncMock()))
    monkeypatch.setattr(seed, "_conflict_rooms", AsyncMock(return_value={"conflict-sb-0001-sso"}))
    monkeypatch.setattr(seed, "_channel_or_none", AsyncMock(return_value="channel"))
    monkeypatch.setattr(seed, "_find_in_channel", AsyncMock(return_value=SimpleNamespace()))
    await seed._auto_decide(
        settings,
        scenario,
        state,
        {"maria": user, "tomas": user},
        [],
        set(),
        "unused",
        "switch",
        hooks=Hooks(),
    )
    assert events == [
        scenario.decision.propose["text"],
        "takeover verified",
        "confirm",
        "restart and duplicate verified",
    ]


@pytest.fixture
async def recovered_demo(tmp_path: Path, llm_factory: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    primary, item, primary_agent = await open_arbiter()
    await propose(primary)
    primary_agent.state.holders = ["splitbrain-arbiter"]
    standby_agent = FakeSwitch("splitbrain-arbiter-b", primary_agent.state)
    standby = arbiter_for(standby_agent)
    group = fake_group()
    observer = FakeSwitch("splitbrain-sentinel", primary_agent.state)
    decision = seed.SeedDecision(
        propose={"as": "maria", "text": "decision: SSO in Q1"},
        confirm={"as": "tomas", "text": "confirm"},
    )
    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    controller = recovery_demo.RecoveryDemo(
        SimpleNamespace(),
        state,
        group,
        observer,
        tmp_path,
        {demo_faults.ENV_VAR: demo_faults.SENTINEL_AFTER_FIRST},
        decision,
    )
    group.child("sentinel").expected_returncode = demo_faults.EXIT_CODE
    original_stop = group.stop_child

    async def stop_primary(name: str) -> None:
        await original_stop(name)
        primary.is_holder = False
        primary_agent.state.holders = []
        await standby._ensure_role()
        group.child("arbiter-b").recent.append("Reused #conflict-sb-0001-sso: record adopted")

    monkeypatch.setattr(group, "stop_child", stop_primary)
    monkeypatch.setattr(recovery_demo, "DUPLICATE_SETTLE_S", 0)
    await controller.before_confirm("conflict-sb-0001-sso")
    assert not standby.verifications["sb-0001"].decided
    primary_agent.state.add_message("r-conflict", "confirm", "tomas")
    await standby.on_frame(human("tomas", "confirm"))
    packet = standby._decision_packet(standby.verifications["sb-0001"])
    faulted = sentinel_for(observer, llm_factory, tmp_path)
    monkeypatch.setenv(demo_faults.ENV_VAR, demo_faults.SENTINEL_AFTER_FIRST)

    def crash(code: int) -> None:
        group.child("sentinel").proc.returncode = code
        raise SystemExit(code)

    monkeypatch.setattr(demo_faults.os, "_exit", crash)
    try:
        with pytest.raises(SystemExit):
            await faulted.on_frame(decision_frame(packet))
    finally:
        await faulted.aclose()
    restarted_agent = FakeSwitch("splitbrain-sentinel", primary_agent.state)
    restarted = sentinel_for(restarted_agent, llm_factory, tmp_path)

    async def restart(name: str, root: Path, env: dict[str, str]) -> demo.Child:
        assert demo_faults.ENV_VAR not in env
        monkeypatch.delenv(demo_faults.ENV_VAR)
        group.child(name).proc = FakeProcess()
        group.child(name).expected_returncode = None
        await restarted.on_frame(decision_frame(packet))
        await standby._publish_decision(standby.verifications["sb-0001"], retry=True)
        return group.child(name)

    async def repeat() -> None:
        primary_agent.state.add_message("r-conflict", "confirm", "tomas")
        await standby.on_frame(human("tomas", "confirm", ident="sw-duplicate", ts=5000))

    monkeypatch.setattr(group, "restart_child", restart)
    monkeypatch.setattr(controller, "_repeat_confirmation", repeat)
    try:
        await controller.after_confirm("conflict-sb-0001-sso")
        yield controller, primary_agent.state, restarted_agent
    finally:
        await restarted.aclose()


async def test_recovery_verifies_all_three_failures_using_switch_documents_and_threads(
    recovered_demo: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    controller, _, restarted = recovered_demo
    report = controller.report
    assert report.room_count == report.decision_count == report.proposal_version == 1
    assert report.correction_counts == [1, 1]
    assert report.checkpoint_statuses == ["posted", "pending"]
    assert report.decision_sender == "splitbrain-arbiter-b"
    assert report.adopted_author == "maria" and report.adopted_confirmations == 0
    assert report.repeated_confirmations == 2
    assert len(report.recovery_document_ids) == 1
    assert [post["room_id"] for post in restarted.posts] == ["r-engineering"]
    report.print_summary()
    output = capsys.readouterr().out
    assert "RECOVERY SUMMARY" in output
    assert "from the room document" in output
    assert "only lets a document's creator edit it" in output
    assert "no new document" not in output


@pytest.mark.parametrize(
    "duplicate", ["room", "proposal", "decision", "correction", "decision_text", "snapshot_case"]
)
async def test_recovery_detects_duplicate_results_in_switch(
    duplicate: str, recovered_demo: Any
) -> None:
    controller, state, _ = recovered_demo
    if duplicate == "room":
        state.rooms["r-duplicate"] = "conflict-sb-9999-sso"
    elif duplicate == "proposal":
        state.add_message("r-conflict", "Proposal v2 from @maria", "splitbrain-arbiter-b")
    elif duplicate == "decision":
        state.add_message("r-conflict", "Decision recorded: duplicate", "splitbrain-arbiter-b")
    elif duplicate == "correction":
        previous = state.threads["r-sales"][0]["replies"][-1]
        state.add_message("r-sales", previous["body"], "splitbrain-sentinel", thread_id="sw_maria")
    elif duplicate == "decision_text":
        for thread in state.threads["r-conflict"]:
            if thread["root"]["body"].startswith("Decision recorded:"):
                thread["root"]["body"] = 'Decision recorded: "A different decision" (confirmed)'
    else:
        for document in state.documents.values():
            if document["owner"] == "splitbrain-arbiter-b":
                document["content"] = document["content"].replace(
                    '"id":"sb-0001"', '"id":"sb-9999"'
                )
        with pytest.raises(SplitbrainError, match="expected valid snapshots for sb-0001"):
            await controller.observe()
        return
    observed = await controller.observe()
    with pytest.raises(SplitbrainError, match="Recovery expected"):
        controller._require_complete(observed)
