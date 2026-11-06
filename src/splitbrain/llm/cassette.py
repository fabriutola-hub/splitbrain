"""Semantic, per-item record/replay cache for model responses.

Cassette keys depend only on the meaning of one item (one normalized message for
extraction, one ordered pair of claims for classification), never on batching,
wall-clock time or request order. Replay therefore needs no network at all.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import SplitbrainError

EXTRACT_PREFIX = "extract|v1|"
CLASSIFY_PREFIX = "classify|v1|"
TASKS = ("extract", "classify")


def normalize_text(text: str) -> str:
    """Canonical form of a chat body used for semantic cache keys."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _digest(prefix: str, payload: str) -> str:
    return hashlib.sha256((prefix + payload).encode("utf-8")).hexdigest()


def extract_key(body: str) -> str:
    return _digest(EXTRACT_PREFIX, normalize_text(body))


def classify_key(claim_a_key: str, claim_b_key: str) -> str:
    return _digest(CLASSIFY_PREFIX, "|".join(sorted((claim_a_key, claim_b_key))))


class ReplayMiss(SplitbrainError):
    """No recorded model response exists for this item in replay mode."""

    def __init__(self, task: str, key: str, description: str) -> None:
        self.task = task
        self.key = key
        self.description = description
        super().__init__(
            f"Replay miss for {task!r} ({description}); expected "
            f"cassettes/{task}/{key}.json. Put SPLITBRAIN_LLM_API_KEY in .env.local, then run "
            "'uv run splitbrain record --missing' to add the cassette, or set "
            "SPLITBRAIN_LLM_MODE=record in .env.local and rerun, or pass --mode live."
        )


class CassetteStore:
    """Reads (replay) and writes (record) `cassettes/<task>/<hash>.json`."""

    def __init__(self, root: Path, *, model: str, mode: str, overwrite: bool = True) -> None:
        self.root = root
        self.model = model
        self.mode = mode
        self.overwrite = overwrite

    def path(self, task: str, key: str) -> Path:
        if task not in TASKS:
            raise ValueError(f"Unknown cassette task: {task!r}")
        return self.root / task / f"{key}.json"

    def has(self, task: str, key: str) -> bool:
        return self.path(task, key).is_file()

    def read_record(self, task: str, key: str, description: str) -> dict[str, Any]:
        try:
            payload = json.loads(self.path(task, key).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ReplayMiss(task, key, description) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("output"), dict):
            raise ReplayMiss(task, key, description)
        return payload

    def read(self, task: str, key: str, description: str) -> dict[str, Any]:
        return dict(self.read_record(task, key, description)["output"])

    def write(
        self,
        task: str,
        key: str,
        input_payload: dict[str, Any],
        output: dict[str, Any],
    ) -> None:
        # `live` never writes; `replay` never reaches this method.
        if self.mode != "record":
            return
        path = self.path(task, key)
        if not self.overwrite and path.is_file():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "task": task,
            "model": self.model,
            "input": input_payload,
            "output": output,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
