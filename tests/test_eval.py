"""Dataset contract and metric / report computation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from splitbrain import cli, evaluation
from splitbrain.config import LLMSettings, SplitbrainError
from splitbrain.core.models import EvalPair, EvalSide, Relation
from splitbrain.core.pipeline import PairResult
from splitbrain.evaluation import (
    LABELS,
    EvalPairV2,
    build_live_run_record,
    compute_metrics,
    load_dataset,
    load_dataset_v2,
    load_live_runs,
    render_live_markdown,
    render_markdown,
    resolve_dataset,
    resolve_mode,
    run,
)
from splitbrain.llm.client import LLMCallStats

DATASET = Path(__file__).resolve().parents[1] / "eval" / "dataset.jsonl"
V2_DATASET = Path(__file__).resolve().parents[1] / "eval" / "dataset-v2.jsonl"


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


class _FakeEvalTransport:
    def __init__(self, *, report_usage: bool = True) -> None:
        self.call_latencies_s = [0.25, 0.35]
        self.prompt_tokens = 400 if report_usage else 0
        self.completion_tokens = 80 if report_usage else 0
        self.total_tokens = 480 if report_usage else 0
        self.usage_calls = 2 if report_usage else 0

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if "<claim " not in user:
            return {
                "results": [
                    {
                        "message_id": "c01-a",
                        "claims": [
                            {
                                "kind": "commitment",
                                "subject": "SSO",
                                "subject_key": "sso",
                                "scope": "all customers",
                                "scope_key": "all",
                                "value": "December 1",
                                "polarity": "affirm",
                                "effective_date": "2026-12-01",
                            }
                        ],
                    },
                    {
                        "message_id": "c01-b",
                        "claims": [
                            {
                                "kind": "commitment",
                                "subject": "SSO",
                                "subject_key": "sso",
                                "scope": "all customers",
                                "scope_key": "all",
                                "value": "Q1 2027",
                                "polarity": "affirm",
                                "effective_date": "2027-01-01",
                            }
                        ],
                    },
                ]
            }
        return {
            "relation": "contradiction",
            "confidence": 0.95,
            "reason": "December 1 vs Q1 2027",
        }

    async def aclose(self) -> None:
        return None


async def test_live_eval_writes_results_live_without_touching_results_md_or_cassettes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "secret-live-key")
    monkeypatch.setenv("SPLITBRAIN_LLM_BASE_URL", "https://api.river.ai/v1")
    monkeypatch.setenv("SPLITBRAIN_LLM_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash-1017")
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir(parents=True)
    pair = EvalPair(
        id="c01",
        a=EvalSide(
            room="sales",
            author="maria",
            text="We promised Enterprise SSO on December 1 for every customer.",
        ),
        b=EvalSide(
            room="engineering",
            author="owen",
            text="Enterprise SSO is slipping to Q1 2027 for all customers.",
        ),
        label=Relation.CONTRADICTION,
        note="release date conflict",
    )
    (eval_dir / "dataset.jsonl").write_text(pair.model_dump_json() + "\n", encoding="utf-8")
    results_md = eval_dir / "results.md"
    results_md.write_text("do not touch me\n", encoding="utf-8")

    for _ in range(3):
        await run("live", transport=_FakeEvalTransport(report_usage=True))

    assert results_md.read_text(encoding="utf-8") == "do not touch me\n"
    assert not (tmp_path / "cassettes").exists()
    live_md = eval_dir / "results-live.md"
    assert live_md.is_file()
    content = live_md.read_text(encoding="utf-8")
    assert "secret-live-key" not in content
    assert "deepseek-ai/DeepSeek-V4.1-Flash-1017" in content
    assert "https://api.river.ai/v1" in content
    assert "## Summary across live runs" in content
    assert "| **Mean** |" in content
    assert "## Run 1 —" in content
    assert "## Run 2 —" in content
    assert "## Run 3 —" in content
    assert "400 / 80 / 480" in content
    loaded = load_live_runs(live_md)
    assert len(loaded) == 3


def test_render_live_markdown_notes_when_tokens_not_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "secret-live-key")
    settings = LLMSettings.load(mode="live")
    pairs = [
        EvalPair(
            id="1",
            a=EvalSide(room="sales", author="maria", text="SSO ships December 1 for all."),
            b=EvalSide(room="ops", author="dana", text="SSO is not shipping in December."),
            label=Relation.CONTRADICTION,
            note="first",
        )
    ]
    metrics = compute_metrics([_result("1", "contradiction", "unrelated")])
    record = build_live_run_record(
        metrics,
        settings=settings,
        duration_s=12.5,
        call_stats=LLMCallStats(calls=2, mean_latency_s=0.45, total_latency_s=0.9),
        run_utc="2026-11-06T00:00:00+00:00",
    )
    text = render_live_markdown([record], settings=settings, pairs=pairs)
    assert "not returned by the API endpoint" in text
    assert "not returned by API" in text
    assert "#### 1 — label `contradiction`, predicted `unrelated`" in text
    assert "secret-live-key" not in text


def test_dataset_v2_contract_and_distribution() -> None:
    pairs = load_dataset_v2(V2_DATASET)
    assert len(pairs) == 100
    labels = Counter(str(pair.label) for pair in pairs)
    assert labels == Counter({"contradiction": 35, "update": 15, "compatible": 25, "unrelated": 25})
    langs = Counter(pair.lang for pair in pairs)
    assert langs == Counter({"en": 70, "es": 18, "mixed": 12})
    assert len({pair.id for pair in pairs}) == 100
    assert all(isinstance(pair, EvalPair) for pair in pairs)
    for pair in pairs:
        assert pair.lang in ("en", "es", "mixed")
        assert pair.tags and all(isinstance(tag, str) and tag.strip() for tag in pair.tags)
        assert pair.note
        assert pair.a.room != pair.b.room
        for side in (pair.a, pair.b):
            assert len(side.text.split()) >= 5
    lines = [line for line in V2_DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 100
    for line in lines:
        assert set(json.loads(line)) == {"id", "a", "b", "label", "note", "lang", "tags"}
    text = V2_DATASET.read_text(encoding="utf-8").casefold()
    for forbidden in ("acme", "globex", "sso", "refund", "99.9", "99.5"):
        assert forbidden not in text


def test_load_dataset_v2_parses_lang_and_tags() -> None:
    pairs = load_dataset_v2(V2_DATASET)
    by_id = {pair.id: pair for pair in pairs}
    assert by_id["v001"].lang == "en"
    assert by_id["v001"].tags == ["pricing", "currency", "relative-date"]
    assert by_id["v005"].lang == "es"
    assert by_id["v010"].lang == "mixed"
    assert str(by_id["v010"].label) == "contradiction"
    assert sum("question" in pair.tags for pair in pairs) >= 6
    assert sum("hypothetical" in pair.tags for pair in pairs) >= 6
    assert sum("own-correction" in pair.tags for pair in pairs) >= 8
    assert sum("authorized-exception" in pair.tags for pair in pairs) >= 6
    assert sum("beta-ga" in pair.tags for pair in pairs) >= 8
    assert sum("relative-date" in pair.tags for pair in pairs) >= 8
    assert (
        sum("different-customer" in pair.tags or "different-region" in pair.tags for pair in pairs)
        >= 6
    )


def test_load_dataset_v2_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(SplitbrainError, match="missing"):
        load_dataset_v2(tmp_path / "nope.jsonl")
    good = {
        "id": "x1",
        "a": {"room": "pricing", "author": "nadia", "text": "The surcharge is 40 USD from Monday."},
        "b": {"room": "billing", "author": "ravi", "text": "The surcharge is 40 EUR from Monday."},
        "label": "contradiction",
        "note": "currency mismatch",
        "lang": "en",
        "tags": ["currency"],
    }
    variants = [
        {key: value for key, value in good.items() if key != "lang"},
        {**good, "lang": "fr"},
        {**good, "tags": []},
        {**good, "tags": ["currency", " "]},
        {**good, "extra": 1},
    ]
    for index, payload in enumerate(variants):
        path = tmp_path / f"bad{index}.jsonl"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(SplitbrainError, match="bad"):
            load_dataset_v2(path)
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(json.dumps(good) + "\n" + json.dumps(good) + "\n", encoding="utf-8")
    with pytest.raises(SplitbrainError, match="duplicate"):
        load_dataset_v2(duplicate)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(SplitbrainError, match="empty"):
        load_dataset_v2(empty)


def test_resolve_dataset_keeps_release_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    settings = LLMSettings.load(mode="replay")
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "dataset-v2.jsonl").write_text("", encoding="utf-8")
    path, display, suffix = resolve_dataset(settings, None)
    assert path == eval_dir / "dataset.jsonl"
    assert (display, suffix) == ("eval/dataset.jsonl", "")
    path, display, suffix = resolve_dataset(settings, "eval/dataset-v2.jsonl")
    assert path == eval_dir / "dataset-v2.jsonl"
    assert (display, suffix) == ("eval/dataset-v2.jsonl", "-v2")


def test_cli_dataset_flag_defaults_to_none() -> None:
    assert cli.build_parser().parse_args(["eval"]).dataset is None
    args = cli.build_parser().parse_args(
        ["eval", "--dataset", "eval/dataset-v2.jsonl", "--mode", "live"]
    )
    assert args.dataset == "eval/dataset-v2.jsonl"
    assert args.mode == "live"


def _stub_pair() -> EvalPair:
    return EvalPair(
        id="c01",
        a=EvalSide(
            room="sales",
            author="maria",
            text="We promised Enterprise SSO on December 1 for every customer.",
        ),
        b=EvalSide(
            room="engineering",
            author="owen",
            text="Enterprise SSO is slipping to Q1 2027 for all customers.",
        ),
        label=Relation.CONTRADICTION,
        note="stub pair",
    )


async def test_without_dataset_behaviour_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "secret-live-key")
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    calls: list[Path] = []

    def spy(path: Path) -> list[EvalPair]:
        calls.append(path)
        return [_stub_pair()]

    def no_v2(path: Path) -> list[EvalPairV2]:
        raise AssertionError("v2 loader must not run without --dataset")

    monkeypatch.setattr(evaluation, "load_dataset", spy)
    monkeypatch.setattr(evaluation, "load_dataset_v2", no_v2)
    await run("live", reset_live=True, transport=_FakeEvalTransport(report_usage=True))

    assert calls == [eval_dir / "dataset.jsonl"]
    assert "1 pairs from eval/dataset.jsonl" in capsys.readouterr().out
    release = (eval_dir / "results-live.md").read_text(encoding="utf-8")
    assert "- Dataset: `eval/dataset.jsonl`" in release
    assert "Language mix" not in release
    assert not (eval_dir / "results-v2-live.md").exists()
    assert not (eval_dir / "results.md").exists()
    assert not (tmp_path / "cassettes").exists()


async def test_dataset_flag_writes_v2_live_report_with_language_mix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "secret-live-key")
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "dataset-v2.jsonl").write_text("{}\n", encoding="utf-8")
    (eval_dir / "results.md").write_text("do not touch\n", encoding="utf-8")
    (eval_dir / "results-live.md").write_text("do not touch either\n", encoding="utf-8")
    calls: list[Path] = []

    def spy(path: Path) -> list[EvalPairV2]:
        calls.append(path)
        return [
            EvalPairV2(
                id="c01",
                a=EvalSide(
                    room="sales",
                    author="maria",
                    text="We promised Enterprise SSO on December 1 for every customer.",
                ),
                b=EvalSide(
                    room="engineering",
                    author="owen",
                    text="Enterprise SSO is slipping to Q1 2027 for all customers.",
                ),
                label=Relation.CONTRADICTION,
                note="stub v2 pair",
                lang="es",
                tags=["currency", "relative-date"],
            )
        ]

    def no_release(path: Path) -> list[EvalPair]:
        raise AssertionError("release loader must not run with --dataset")

    monkeypatch.setattr(evaluation, "load_dataset_v2", spy)
    monkeypatch.setattr(evaluation, "load_dataset", no_release)
    await run(
        "live",
        dataset="eval/dataset-v2.jsonl",
        reset_live=True,
        transport=_FakeEvalTransport(report_usage=True),
    )

    assert calls == [eval_dir / "dataset-v2.jsonl"]
    assert "1 pairs from eval/dataset-v2.jsonl" in capsys.readouterr().out
    report = (eval_dir / "results-v2-live.md").read_text(encoding="utf-8")
    assert "- Dataset: `eval/dataset-v2.jsonl`" in report
    assert "- Language mix: es=1" in report
    assert "secret-live-key" not in report
    assert (eval_dir / "results.md").read_text(encoding="utf-8") == "do not touch\n"
    assert (eval_dir / "results-live.md").read_text(encoding="utf-8") == "do not touch either\n"
    assert not (eval_dir / "results-v2.md").exists()
    assert not (tmp_path / "cassettes").exists()


async def test_dataset_flag_with_the_release_dataset_uses_the_release_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "secret-live-key")
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "dataset.jsonl").write_text("", encoding="utf-8")
    calls: list[Path] = []

    def spy(path: Path) -> list[EvalPair]:
        calls.append(path)
        return [_stub_pair()]

    def no_v2(path: Path) -> list[EvalPairV2]:
        raise AssertionError("v2 loader must not run for eval/dataset.jsonl")

    monkeypatch.setattr(evaluation, "load_dataset", spy)
    monkeypatch.setattr(evaluation, "load_dataset_v2", no_v2)
    await run(
        "live",
        dataset="eval/dataset.jsonl",
        reset_live=True,
        transport=_FakeEvalTransport(report_usage=True),
    )

    assert calls == [eval_dir / "dataset.jsonl"]
    assert "1 pairs from eval/dataset.jsonl" in capsys.readouterr().out
    report = (eval_dir / "results-live.md").read_text(encoding="utf-8")
    assert "- Dataset: `eval/dataset.jsonl`" in report
    assert not (eval_dir / "results-v2-live.md").exists()
