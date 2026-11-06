"""Demo modes, clean-state guard, scenario evidence, times and banners."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from splitbrain import bootstrap, demo, recording, seed
from splitbrain.agents import arbiter as arbiter_module
from splitbrain.config import Paths, SplitbrainError
from splitbrain.core.models import Claim, Evidence, EvidenceItem
from splitbrain.core.store import ClaimStore
from splitbrain.core.timefmt import resolve_zone, stamp, stamp_iso, zone_label
from splitbrain.evidence import scenario as scenario_evidence
from splitbrain.evidence.github import FIXTURE_BANNER, GitHubSnapshot, build_evidence
from splitbrain.llm.cassette import normalize_text

ROOT = Path(__file__).resolve().parents[1]


def _paths() -> Paths:
    return Paths.default()


@pytest.fixture(autouse=True)
def _fake_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests exercise demo modes, not the Docker CLI; Settings.load still needs one."""
    fake_docker = tmp_path / "docker"
    fake_docker.touch()
    monkeypatch.setenv("SPLITBRAIN_DOCKER", str(fake_docker))


# ── Modes and banners ──────────────────────────────────────────────────────


def test_offline_forces_replay_and_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    modes = demo.resolve_modes(offline=True, scenario="sso", paths=_paths())
    assert modes.llm_mode == "replay"
    assert modes.evidence_mode == "fixture"
    assert any("[DEGRADED] LLM replay" in line for line in modes.degraded)
    assert FIXTURE_BANNER in modes.degraded
    env = demo.child_environment(modes)
    assert env["SPLITBRAIN_LLM_MODE"] == "replay"
    assert env["SPLITBRAIN_EVIDENCE_MODE"] == "fixture"


def test_no_key_defaults_to_replay_and_live_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "")
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(ROOT))
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    # Only the process env matters here; .env.local may hold a developer key.
    modes = demo.resolve_modes(offline=False, scenario="sso", paths=_paths())
    assert modes.llm_mode == "replay"
    assert modes.evidence_mode == "live"
    assert any("[DEGRADED] LLM replay" in line for line in modes.degraded)


def test_hackathon_announces_its_scenario_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    modes = demo.resolve_modes(offline=True, scenario="hackathon", paths=_paths())
    assert modes.scenario_evidence == "hackathon"
    assert any("scenario fixture" in line and "[DEGRADED]" in line for line in modes.degraded)
    assert demo.child_environment(modes)[scenario_evidence.ENV_VAR] == "hackathon"


def test_demo_summary_repeats_degraded_banners(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from splitbrain.config import Settings

    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    modes = demo.resolve_modes(offline=True, scenario="sso", paths=_paths())
    settings = Settings.load(require_env_file=False)
    state = bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(room_id=f"r-{name}", channel_type="channel_public")
            for name in bootstrap.STATE_ROOMS
        },
        mattermost=bootstrap.MattermostState(password="demo-password"),
    )
    demo.print_summary(
        settings=settings,
        state=state,
        modes=modes,
        scenario="sso",
        conflict_room="conflict-sb-1234-sso",
        decision={"text": "SSO beta on Dec 15", "proposed_by": "maria", "confirmed_by": "tomas"},
        corrections=["sales", "engineering"],
        note="full loop closed by --auto-decide",
    )
    output = capsys.readouterr().out
    assert "DEMO SUMMARY" in output
    assert "Conflict:      sb-1234" in output
    assert 'Decision:      "SSO beta on Dec 15"' in output
    assert "Corrections:   #sales, #engineering" in output
    assert "login=maria / demo-password" in output
    assert "login=tomas / demo-password" in output
    assert "[DEGRADED] LLM replay" in output
    assert FIXTURE_BANNER in output
    assert "hackathon-prizes" in output


# ── Clean state ────────────────────────────────────────────────────────────


def _claim(room: str, author: str, text: str) -> Claim:
    return Claim(
        id=f"clm_{room}_{author}",
        room_id=f"r-{room}",
        room_name=room,
        message_id=f"sw_{room}",
        author=author,
        text=text,
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        value="December 1",
    )


async def test_seed_refuses_only_a_repeat_of_the_same_scenario(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "sentinel.db")
    try:
        await store.add_claim(_claim("sales", "maria", "SSO live on December 1"))
    finally:
        await store.close()
    fake = SimpleNamespace(paths=SimpleNamespace(root=ROOT, state_dir=tmp_path))
    stub = SimpleNamespace(paths=SimpleNamespace(root=ROOT))
    seed.mark_seeded(fake, "sso")
    # A different scenario runs even with old active claims in the store.
    await seed.check_stale_claims(fake, seed.load_scenario(stub, "near-misses"))
    with pytest.raises(SplitbrainError) as error:
        await seed.check_stale_claims(fake, seed.load_scenario(stub, "sso"))
    message = str(error.value)
    assert "'sso'" in message
    assert "already seeded on this stack" in message
    assert "down --wipe" in message
    assert "sentinel.db" in message


async def test_seed_allows_a_clean_store(tmp_path: Path) -> None:
    fake = SimpleNamespace(paths=SimpleNamespace(root=ROOT, state_dir=tmp_path))
    scenario = seed.load_scenario(SimpleNamespace(paths=SimpleNamespace(root=ROOT)), "sso")
    await seed.check_stale_claims(fake, scenario)


def test_synthetic_state_covers_every_demo_room() -> None:
    state = seed.synthetic_state()
    assert set(bootstrap.STATE_ROOMS) <= set(state.rooms)
    assert state.rooms["engineering"].channel_type == "channel_private"


# ── Scenarios, template and cassettes ──────────────────────────────────────


def test_refunds_and_hackathon_scenarios_are_consistent() -> None:
    stub = SimpleNamespace(paths=SimpleNamespace(root=ROOT))
    refunds = seed.load_scenario(stub, "refunds")
    assert {m.person for m in refunds.messages} >= {"lucia", "pablo"}
    assert {m.room for m in refunds.messages} >= {"support", "finance"}
    assert refunds.decision is not None
    assert refunds.decision.propose["as"] == "lucia"
    assert "$500" in refunds.messages[0].text and "$250" in refunds.messages[-1].text

    hackathon = seed.load_scenario(stub, "hackathon")
    assert hackathon.decision is None
    assert [m.room for m in hackathon.messages] == ["hackathon-prizes", "hackathon-judging"]
    assert [m.person for m in hackathon.messages] == ["page-prizes", "page-judging"]
    assert "up to 20 merged pull requests" in hackathon.messages[0].text
    assert "the 10 best pull requests" in hackathon.messages[1].text


def test_hackathon_template_creates_two_public_rooms() -> None:
    import yaml

    text = (ROOT / "templates" / "hackathon.template.yaml").read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    assert document["version"] == 1
    by_name = {room["name"]: room for room in document["rooms"]}
    assert set(by_name) == set(bootstrap.HACKATHON_ROOMS)
    for room in by_name.values():
        assert room["channel_type"] == "channel_public"
        assert "fabrizio" in room["users"]
        assert "splitbrain-sentinel" in room["agents"]
    assert "page-prizes" in by_name["hackathon-prizes"]["users"]
    assert "page-judging" in by_name["hackathon-judging"]["users"]


def test_no_scenario_line_shadows_an_eval_line() -> None:
    recording.assert_scenarios_do_not_shadow_eval(ROOT)
    eval_texts = {
        normalize_text(json.loads(line)[side]["text"])
        for line in (ROOT / "eval" / "dataset.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for side in ("a", "b")
    }
    for name in recording.SCENARIOS:
        for message in seed.load_scenario(
            SimpleNamespace(paths=SimpleNamespace(root=ROOT)), name
        ).messages:
            assert normalize_text(message.text) not in eval_texts


# ── Scenario evidence (honest, explicit) ───────────────────────────────────


def test_scenario_evidence_is_explicit_and_not_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(scenario_evidence.ENV_VAR, raising=False)
    assert scenario_evidence.load_scenario_evidence(_paths()) is None
    entry = scenario_evidence.load_entry("hackathon", _paths())
    assert "[DEGRADED]" in entry.banner()
    assert entry.matches("Track 3 Best Core Contribution")
    assert not entry.matches("SSO rollout date")
    evidence = entry.evidence("sb-0001")
    assert evidence.source == "scenario_fixture"
    assert evidence.status == "conflicting"
    assert evidence.summary == f"Ambiguous: {entry.summary}"
    assert "20 merged pull requests" in evidence.summary
    assert "not a GitHub issue" in evidence.detail
    already_labeled = scenario_evidence.ScenarioEvidence(
        name=entry.name,
        label=entry.label,
        keywords=entry.keywords,
        summary="Ambiguous: already labelled",
        detail=entry.detail,
        items=entry.items,
    )
    assert already_labeled.evidence("sb-0002").summary == "Ambiguous: already labelled"
    monkeypatch.setenv(scenario_evidence.ENV_VAR, "hackathon")
    assert scenario_evidence.load_scenario_evidence(_paths()) == entry


def test_bad_scenario_evidence_name_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(scenario_evidence.ENV_VAR, "not-a-scenario")
    with pytest.raises(SplitbrainError, match="has no entry"):
        scenario_evidence.load_scenario_evidence(_paths())


def test_brief_names_the_evidence_source_only_once() -> None:
    from splitbrain.core.protocol import CandidatePacket, PacketClaim

    def claim(author: str, room: str) -> PacketClaim:
        return PacketClaim(
            id=f"clm_{author}",
            room_id=f"r-{room}",
            room_name=room,
            message_id=f"sw_{author}",
            author=author,
            text="SSO live on December 1",
            subject="SSO",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            value="December 1",
        )

    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    arbiter = arbiter_module.Arbiter(
        agent=object(),  # type: ignore[arg-type]
        state=state,
        name=arbiter_module.AGENT_NAME,
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )
    item = arbiter_module.Verification(
        candidate=CandidatePacket(
            id="sb-0001",
            claim_a=claim("maria", "sales"),
            claim_b=claim("tomas", "engineering"),
            confidence=0.93,
        ),
        thread_id="sw-root",
        requested_at=0.0,
    )
    item.evidence = Evidence(
        candidate_id="sb-0001",
        source="github",
        status="supports_b",
        summary='issue #2 "SSO (SAML / OIDC) for enterprise customers" moved from '
        "Q4 2026 to Q1 2027 on Nov 4.",
        detail="GitHub, fabriutola-hub/splitbrain-demo-roadmap: issue #2 ... "
        "timeline: milestoned Q4 2026 -> demilestoned Q4 2026 -> milestoned Q1 2027.",
        items=[
            EvidenceItem(
                title="#2 SSO",
                url="https://github.com/fabriutola-hub/splitbrain-demo-roadmap/issues/2",
            )
        ],
    )
    brief = arbiter._brief(item)
    evidence_lines = [line for line in brief.splitlines() if line.startswith("Evidence (")]
    assert evidence_lines == [
        "Evidence (GitHub, fabriutola-hub/splitbrain-demo-roadmap): "
        'issue #2 "SSO (SAML / OIDC) for enterprise customers" moved from '
        "Q4 2026 to Q1 2027 on Nov 4."
    ]
    assert "timeline:" not in brief
    record = arbiter._open_record(item)
    assert "timeline:" in record


def test_refund_evidence_points_at_issue_5() -> None:
    snapshot = GitHubSnapshot.model_validate(
        json.loads((ROOT / "seed" / "github_fixture.json").read_text(encoding="utf-8"))
    )
    filtered = snapshot.model_copy(
        update={
            "issues": [
                issue
                for issue in snapshot.issues
                if issue.state == "open" and "refunds" in f"{issue.title} {issue.body}".casefold()
            ]
        }
    )
    evidence = build_evidence(
        "sb-0002",
        "refunds",
        filtered,
        source="fixture",
        claim_a="refunds above $500",
        claim_b="threshold is $250",
    )
    assert evidence.status == "conflicting"
    assert 'issue #5 "Support macros: refunds over $250' in evidence.summary
    assert "GitHub, fabriutola-hub/splitbrain-demo-roadmap" in evidence.detail
    assert "GitHub," not in evidence.summary


# ── Unambiguous times ──────────────────────────────────────────────────────


def test_stamps_are_never_bare_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    import re

    monkeypatch.delenv("SPLITBRAIN_TZ", raising=False)
    local = stamp(1793776781000)
    assert re.search(r"UTC[+-]\d{2}:\d{2}$", local)
    assert zone_label().startswith("Local time (UTC")
    from datetime import UTC, datetime

    assert stamp_iso(datetime.fromtimestamp(1793776781, UTC).isoformat()) == local

    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    caracas = stamp(1793776781000)
    assert caracas.endswith("UTC-04:00")
    assert "America/Caracas" in zone_label()
    assert caracas.split()[-2] != local.split()[-2] or local.endswith("UTC-04:00")
    monkeypatch.setenv("SPLITBRAIN_TZ", "Mars/Olympus")
    with pytest.raises(SplitbrainError, match="not a valid IANA time zone"):
        resolve_zone()


def test_brief_times_carry_a_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    from splitbrain.agents import arbiter

    monkeypatch.delenv("SPLITBRAIN_TZ", raising=False)
    assert "UTC" in arbiter.stamp(1793776781000)
    assert "UTC" in arbiter.stamp_iso("2026-11-05T03:18:00+00:00")


async def test_open_conflict_reuses_a_room_that_already_exists() -> None:
    """Idempotency: never call create_room twice for one candidate id."""
    from splitbrain.agents import arbiter as arbiter_module
    from splitbrain.core.protocol import CandidatePacket, PacketClaim

    def claim(author: str, room: str) -> PacketClaim:
        return PacketClaim(
            id=f"clm_{author}",
            room_id=f"r-{room}",
            room_name=room,
            message_id=f"sw_{author}",
            author=author,
            text="SSO live on December 1",
            subject="SSO",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            value="December 1",
        )

    class FakeAgent:
        def __init__(self) -> None:
            self.calls: list[str] = []

        @asynccontextmanager
        async def act_in(self, room_id: str):
            yield self

        async def op(self, name: str, /, **kwargs: Any) -> Any:
            self.calls.append(name)
            if name == "list_all_rooms":
                return [{"name": "conflict-sb-0001-sso", "room_id": "r-existing"}]
            if name == "read_context":
                return {
                    "threads": [
                        {
                            "root": {"body": "@maria @tomas - Splitbrain found two statements"},
                            "replies": [],
                        }
                    ]
                }
            if name == "connect_to_room":
                return {
                    "documents": [{"id": "doc-1", "name": "SB-0001 decision record"}],
                    "linked_rooms": [{"label": "origin: #sales (maria)"}],
                }
            if name == "load_internal_documents":
                return [{"content": "Status: OPEN"}]
            return {}

    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    fake = FakeAgent()
    arbiter = arbiter_module.Arbiter(
        agent=fake,  # type: ignore[arg-type]
        state=state,
        name="splitbrain-arbiter",
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )
    arbiter.is_holder = True
    verification = arbiter_module.Verification(
        candidate=CandidatePacket(
            id="sb-0001",
            claim_a=claim("maria", "sales"),
            claim_b=claim("tomas", "engineering"),
            confidence=0.93,
        ),
        thread_id="sw-root",
        requested_at=0.0,
    )
    verification.evidence = Evidence(
        candidate_id="sb-0001",
        source="fixture",
        status="supports_b",
        summary="issue #2 moved from Q4 2026 to Q1 2027 on Nov 4",
    )
    await arbiter._open_conflict(verification)
    assert "create_room" not in fake.calls
    assert "create_room_document" not in fake.calls
    assert verification.room_id == "r-existing"
    assert verification.record == "Status: OPEN"
    assert verification.machine is not None


async def test_a_duplicate_arbiter_lease_never_creates_two_alerts() -> None:
    """Switch 0.31.0 grants two simultaneous assume_role calls; only A acts."""
    from splitbrain.agents import arbiter as arbiter_module

    class FakeAgent:
        def __init__(self) -> None:
            self.calls: list[str] = []

        @asynccontextmanager
        async def act_in(self, room_id: str):
            self.calls.append("act_in")
            yield self

        async def op(self, name: str, /, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(name)
            if name == "get_room_detail":
                return {
                    "roles": [
                        {
                            "name": "arbiter",
                            "held_by": [
                                {"name": "splitbrain-arbiter-b"},
                                {"name": "splitbrain-arbiter"},
                            ],
                        }
                    ]
                }
            if name == "release_role":
                return {"status": "released"}
            return {}

    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    standby_agent = FakeAgent()
    standby = arbiter_module.Arbiter(
        agent=standby_agent,  # type: ignore[arg-type]
        state=state,
        name="splitbrain-arbiter-b",
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )
    standby.is_holder = True
    await standby._ensure_role()
    assert standby.is_holder is False
    assert "assume_role" not in standby_agent.calls
    assert "release_role" in standby_agent.calls

    primary_agent = FakeAgent()
    primary = arbiter_module.Arbiter(
        agent=primary_agent,  # type: ignore[arg-type]
        state=state,
        name="splitbrain-arbiter",
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )
    await primary._ensure_role()
    assert primary.is_holder is True
    assert "release_role" not in primary_agent.calls


# ── Human-decision path (no --auto-decide) ─────────────────────────────────


def test_consent_instructions_are_printed_for_private_rooms(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from splitbrain.config import Settings

    settings = Settings.load(require_env_file=False)
    state = seed.synthetic_state()
    stub = SimpleNamespace(paths=SimpleNamespace(root=ROOT))
    demo.print_consent_instructions(seed.load_scenario(stub, "sso"), state, settings)
    output = capsys.readouterr().out
    assert "A person must answer the consent question first" in output
    assert "@tomas" in output and "reply 'yes'" in output
    assert "#engineering" in output
    assert "http://localhost:8065/switch/channels/engineering" in output


def test_public_scenario_prints_no_consent_instructions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from splitbrain.config import Settings

    settings = Settings.load(require_env_file=False)
    stub = SimpleNamespace(paths=SimpleNamespace(root=ROOT))
    demo.print_consent_instructions(
        seed.load_scenario(stub, "refunds"), seed.synthetic_state(), settings
    )
    assert capsys.readouterr().out == ""


def test_decision_instructions_name_both_people_and_the_exact_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from splitbrain.config import Settings

    settings = Settings.load(require_env_file=False)
    stub = SimpleNamespace(paths=SimpleNamespace(root=ROOT))
    scenario = seed.load_scenario(stub, "sso")
    demo.print_decision_instructions(scenario, "conflict-sb-0001-sso", settings)
    output = capsys.readouterr().out
    assert "Waiting for a HUMAN decision in #conflict-sb-0001-sso" in output
    assert "María Gómez (@maria) writes" in output
    assert "decision: <what you agreed>" in output
    assert "Tomás Rivera (@tomas) replies" in output
    assert "      confirm" in output
    assert "Only those two can close it" in output
    assert "http://localhost:8065/switch/channels/conflict-sb-0001-sso" in output


def test_human_timeouts_cover_the_default_consent_timeout() -> None:
    # The Arbiter waits 600 s for consent before opening the room; the demo
    # must wait longer than that for both the room and the human decision.
    assert demo.HUMAN_CONFLICT_TIMEOUT_S >= 600.0
    assert demo.HUMAN_DECISION_TIMEOUT_S >= 600.0
    assert demo.HUMAN_CONFLICT_TIMEOUT_S > demo.CONFLICT_TIMEOUT_S
