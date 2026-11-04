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
from .agents.sentinel import Sentinel
from .config import LLMSettings, SplitbrainError
from .core.models import Message
from .core.store import ClaimStore
from .llm.cassette import CassetteStore, normalize_text
from .llm.client import LLMClient

SCENARIOS: tuple[str, ...] = ("sso", "refunds", "hackathon", "near-misses")


class Sink:
    """A SwitchAgent stand-in that records targeted posts and nothing else."""

    agent_id = "record-sink"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def op(self, name: str, /, **kwargs: Any) -> list[Any]:
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


def _cassette_counts(root: Path) -> dict[str, int]:
    folder = root / "cassettes"
    return {
        task: len(list((folder / task).glob("*.json"))) if (folder / task).is_dir() else 0
        for task in ("extract", "classify")
    }


async def record_all() -> None:
    settings = LLMSettings.load(mode="record")
    root = settings.cassettes_dir.parent
    assert_scenarios_do_not_shadow_eval(root)
    before = _cassette_counts(root)
    print(
        f"[RECORD] model={settings.model} base_url={settings.base_url} "
        "— evaluation and 4 seed scenarios",
        flush=True,
    )
    await evaluation.run("record")
    for name in SCENARIOS:
        cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode="record")
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
