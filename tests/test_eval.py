"""Dataset contract (SPEC 4.11) and metric / report computation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from splitbrain.config import SplitbrainError
from splitbrain.core.models import EvalPair, EvalSide, Relation
from splitbrain.core.pipeline import PairResult
from splitbrain.evaluation import (
    LABELS,
    compute_metrics,
    load_dataset,
    render_markdown,
    resolve_mode,
)

DATASET = Path(__file__).resolve().parents[1] / "eval" / "dataset.jsonl"


def _result(identifier: str, label: str, predicted: str) -> PairResult:
    return PairResult(
        id=identifier,
        label=label,
        predicted=predicted,
        relation=predicted,
        confidence=0.9,
        reason="unit test",
        stage="classification",
        candidate=predicted == "contradiction",
        note="unit test",
    )


def test_compute_metrics_and_confusion_matrix() -> None:
    results = [
        _result("1", "contradiction", "contradiction"),
        _result("2", "contradiction", "unrelated"),
        _result("3", "unrelated", "contradiction"),
        _result("4", "compatible", "compatible"),
        _result("5", "update", "unrelated"),
    ]
    metrics = compute_metrics(results)
    assert (metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]) == (1, 1, 1, 2)
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["f1"] == pytest.approx(0.5)
    assert metrics["matrix"][("contradiction", "contradiction")] == 1
    assert metrics["matrix"][("contradiction", "unrelated")] == 1
    assert len(metrics["errors"]) == 3


def test_perfect_run() -> None:
    results = [_result("1", "contradiction", "contradiction"), _result("2", "update", "update")]
    metrics = compute_metrics(results)
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == 1.0
    assert metrics["errors"] == []


def test_dataset_contract() -> None:
    pairs = load_dataset(DATASET)
    assert len(pairs) >= 40
    labels = Counter(str(pair.label) for pair in pairs)
    assert labels["contradiction"] >= 12
    assert sum(labels[label] for label in LABELS if label != "contradiction") >= 12
    assert all(str(pair.label) in LABELS for pair in pairs)
    assert len({pair.id for pair in pairs}) == len(pairs)
    for pair in pairs:
        assert pair.a.room != pair.b.room, f"{pair.id}: matcher requires different rooms"
        assert pair.note, f"{pair.id}: missing note"
        for side in (pair.a, pair.b):
            assert len(side.text.split()) >= 5, f"{pair.id}: too short for the prefilter"
    near_miss_notes = " ".join(pair.note for pair in pairs if pair.note.startswith("near-miss"))
    assert near_miss_notes.count("near-miss") >= 12
    for category in (
        "different customer",
        "own earlier statement",
        "compatible phases",
        "hypothetical",
        "question",
        "supersedes",
    ):
        assert category in near_miss_notes, category
    assert any("Spanish" in pair.note or "español" in pair.note for pair in pairs)
    assert (
        sum(
            1
            for pair in pairs
            for side in (pair.a, pair.b)
            if any(c in side.text for c in "áéíóúñ¿")
        )
        >= 4
    )
    assert len({str(pair.label) for pair in pairs}) == 4


def test_dataset_lines_are_valid_json_objects() -> None:
    lines = [line for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 40
    for line in lines:
        assert set(json.loads(line)) == {"id", "a", "b", "label", "note"}


def test_load_dataset_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(SplitbrainError, match="missing"):
        load_dataset(tmp_path / "nope.jsonl")
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "x"}\n', encoding="utf-8")
    with pytest.raises(SplitbrainError, match="bad.jsonl:1"):
        load_dataset(bad)


def test_resolve_mode_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    assert resolve_mode(None) == "replay"
    monkeypatch.setenv("SPLITBRAIN_LLM_MODE", "record")
    assert resolve_mode(None) == "record"
    assert resolve_mode("replay") == "replay"
    monkeypatch.setenv("SPLITBRAIN_LLM_MODE", "bogus")
    with pytest.raises(SplitbrainError, match="Evaluation mode"):
        resolve_mode(None)


def test_markdown_report_contains_metrics_matrix_and_errors(tmp_path: Path) -> None:
    from splitbrain.config import LLMSettings

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
        settings = LLMSettings.load(mode="replay")
        metrics = compute_metrics(
            [_result("1", "contradiction", "unrelated"), _result("2", "update", "update")]
        )
        text = render_markdown(
            metrics,
            settings=settings,
            pairs=[
                EvalPair(
                    id="1",
                    a=EvalSide(room="sales", author="maria", text="SSO ships December 1."),
                    b=EvalSide(room="ops", author="dana", text="SSO is not shipping."),
                    label=Relation.CONTRADICTION,
                    note="first",
                ),
                EvalPair(
                    id="2",
                    a=EvalSide(room="sales", author="maria", text="SSO ships December 1."),
                    b=EvalSide(room="ops", author="dana", text="SSO now ships December 15."),
                    label=Relation.UPDATE,
                    note="second",
                ),
            ],
            cassette_counts={"extract": 2, "classify": 1},
            previous_mode=None,
            identical=False,
            marker="<!-- splitbrain-metrics mode=replay p=0 r=0 f1=0 -->",
        )
        assert "## Metrics for `contradiction`" in text
        assert "## Confusion matrix" in text
        assert "## Errors (1)" in text
        assert "label \\ predicted" in text
        assert settings.model in text
        assert "unit-test-key" not in text
    finally:
        monkeypatch.undo()
