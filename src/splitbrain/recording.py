"""`splitbrain record`: refresh the evaluation and all demo cassettes.

The scenario path is the *same* Sentinel pipeline that the live agents run
(prefilter -> extraction -> matching -> classification), with a no-op Switch
sink. Cassette keys depend only on normalized message text and on the sorted
claim keys, so the recordings are valid for the real Switch message ids too.
`record` needs an API key; it never fakes a response.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from . import evaluation, seed
from .agents.sentinel import Sentinel, decision_claim_for
from .config import LLMSettings, SplitbrainError
from .core.decision import PROPOSAL_RE
from .core.models import Claim, Decision, Message
from .core.protocol import DecidedPacket
from .core.store import ClaimStore
from .llm.cassette import CassetteStore, normalize_text
from .llm.client import LLMClient

SCENARIOS: tuple[str, ...] = ("sso", "sso-followup", "refunds", "hackathon", "near-misses")


class Sink:
    """A SwitchAgent stand-in that records targeted posts and nothing else."""

    agent_id = "record-sink"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def op(self, name: str, /, **kwargs: Any) -> Any:
        if name == "connect_to_room":
            return {"documents": [{"id": "doc-record", "name": "SB-0001 decision record"}]}
        if name == "load_internal_documents":
            return [
                {
                    "id": "doc-record",
                    "name": "SB-0001 decision record",
                    "content": (
                        "SB-0001 decision record\n\n"
                        "Status: DECIDED\n"
                        "Decision protocol: only @maria and @tomas can close this conflict."
                    ),
                }
            ]
        return []

    @asynccontextmanager
    async def act_in(self, room_id: str):
        yield self

    async def targeted(self, room_id: str, body: str, **kwargs: Any) -> dict[str, str]:
        self.sent.append((room_id, body))
        return {"event_id": "sw_record"}

    async def post(self, room_id: str, body: str, **kwargs: Any) -> dict[str, str]:
        self.sent.append((room_id, body))
        return {"event_id": "sw_record"}

    async def aclose(self) -> None:
        return None


def _eval_texts(root: Path) -> set[str]:
    path = root / "eval" / "dataset.jsonl"
    if not path.is_file():
        raise SplitbrainError(f"Evaluation dataset is missing: {path}")
    texts: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        pair = json.loads(line)
        texts.add(normalize_text(pair["a"]["text"]))
        texts.add(normalize_text(pair["b"]["text"]))
    return texts


def assert_scenarios_do_not_shadow_eval(root: Path) -> None:
    """A byte-identical seed line would overwrite an eval cassette on record."""
    eval_texts = _eval_texts(root)
    for name in SCENARIOS:
        scenario = seed.load_scenario(_settings_stub(root), name)
        for message in scenario.messages:
            if normalize_text(message.text) in eval_texts:
                raise SplitbrainError(
                    f"Scenario {name!r} reuses an eval line verbatim: {message.text!r}. "
                    "Reword it so recording cannot overwrite an eval cassette."
                )


def _settings_stub(root: Path) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(paths=SimpleNamespace(root=root))


def _scenario_messages(name: str, root: Path) -> list[Message]:
    scenario = seed.load_scenario(_settings_stub(root), name)
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


def sso_decision_claim(root: Path) -> Claim:
    """The DECISION claim that `_apply_corrections` stores after `sso` is decided."""
    scenario = seed.load_scenario(_settings_stub(root), "sso")
    assert scenario.decision is not None
    raw_text = scenario.decision.propose["text"]
    match = PROPOSAL_RE.match(raw_text)
    decision_text = match.group(1) if match else raw_text
    decided = DecidedPacket(
        candidate_id="sb-0001",
        decision=Decision(
            candidate_id="sb-0001",
            room_id="r-conflict-sso",
            text=decision_text,
            proposed_by=scenario.decision.propose["as"],
            confirmed_by=scenario.decision.confirm["as"],
            decided_at="2026-11-05T00:00:00+00:00",
        ),
        conflict_room="r-conflict-sso",
        conflict_room_name="conflict-sb-0001-sso",
        origins=[],
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        authors=[scenario.decision.propose["as"], scenario.decision.confirm["as"]],
    )
    return decision_claim_for(decided)


def _cassette_counts(root: Path) -> dict[str, int]:
    folder = root / "cassettes"
    return {
        task: len(list((folder / task).glob("*.json"))) if (folder / task).is_dir() else 0
        for task in ("extract", "classify")
    }


async def record_all(*, missing_only: bool = False) -> None:
    settings = LLMSettings.load(mode="record")
    root = settings.cassettes_dir.parent
    assert_scenarios_do_not_shadow_eval(root)
    before = _cassette_counts(root)
    mode_note = " (missing cassettes only)" if missing_only else ""
    print(
        f"[RECORD] model={settings.model} base_url={settings.base_url} "
        f"— evaluation and {len(SCENARIOS)} seed scenarios{mode_note}",
        flush=True,
    )
    await evaluation.run("record", overwrite=not missing_only, write_report=not missing_only)
    for name in SCENARIOS:
        cassettes = CassetteStore(
            settings.cassettes_dir,
            model=settings.model,
            mode="record",
            overwrite=not missing_only,
        )
        llm = LLMClient(settings, cassettes)
        sink = Sink()
        state = seed.synthetic_state()
        sentinel = Sentinel(
            agent=sink,  # type: ignore[arg-type]
            llm=llm,
            store=ClaimStore(":memory:"),
            state=state,
            batch_window_s=0.0,
        )
        await sentinel.start()
        try:
            if name == "sso-followup":
                await sentinel.store.add_claim(sso_decision_claim(root))
            await sentinel.analyze_messages(_scenario_messages(name, root))
            print(
                f"[RECORD] scenario {name:<12} messages={sentinel.messages_processed} "
                f"candidates={sentinel.candidates_sent}",
                flush=True,
            )
        finally:
            await sentinel.aclose()
    after = _cassette_counts(root)
    print(
        "[RECORD] cassettes: "
        + ", ".join(
            f"{task} {before[task]} -> {after[task]} (+{after[task] - before[task]})"
            for task in ("extract", "classify")
        ),
        flush=True,
    )
    print("[RECORD] done. Commit cassettes/ so a keyless clone can replay.", flush=True)
