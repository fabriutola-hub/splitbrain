"""`splitbrain eval`: run the detection pipeline over the labeled dataset.

This is the exact path the Sentinel uses (Brain.analyze_pair), so the numbers
below describe what the agent will do in a live room.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import LLM_MODES, LLMSettings, SplitbrainError
from .core.models import EvalPair
from .core.pipeline import Brain, PairResult
from .llm.cassette import CassetteStore
from .llm.client import LLMClient

LABELS: tuple[str, ...] = ("contradiction", "update", "compatible", "unrelated")
METRIC_MARKER = "<!-- splitbrain-metrics {content} -->"


def resolve_mode(cli_mode: str | None) -> str:
    """Explicit --mode wins, then SPLITBRAIN_LLM_MODE, then offline replay."""
    mode = (cli_mode or os.environ.get("SPLITBRAIN_LLM_MODE") or "replay").strip().lower()
    if mode not in LLM_MODES:
        raise SplitbrainError(
            f"Evaluation mode must be one of {', '.join(LLM_MODES)}, got {mode!r}."
        )
    return mode


def load_dataset(path: Path) -> list[EvalPair]:
    if not path.is_file():
        raise SplitbrainError(f"Evaluation dataset is missing: {path}")
    pairs: list[EvalPair] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            pairs.append(EvalPair.model_validate_json(line))
        except ValueError as exc:
            raise SplitbrainError(f"{path}:{number} is not a valid eval pair: {exc}") from exc
    if not pairs:
        raise SplitbrainError(f"Evaluation dataset is empty: {path}")
    return pairs


def compute_metrics(results: list[PairResult]) -> dict[str, Any]:
    tp = sum(r.predicted == "contradiction" and r.label == "contradiction" for r in results)
    fp = sum(r.predicted == "contradiction" and r.label != "contradiction" for r in results)
    fn = sum(r.predicted != "contradiction" and r.label == "contradiction" for r in results)
    tn = sum(r.predicted != "contradiction" and r.label != "contradiction" for r in results)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    matrix = {
        (label, predicted): sum(r.label == label and r.predicted == predicted for r in results)
        for label in LABELS
        for predicted in LABELS
    }
    errors = [r for r in results if r.label != r.predicted]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matrix": matrix,
        "errors": errors,
        "total": len(results),
        "labels": Counter(r.label for r in results),
    }


def _numbers(metrics: dict[str, Any]) -> str:
    return (
        f"p={metrics['precision']:.6f} r={metrics['recall']:.6f} f1={metrics['f1']:.6f} "
        f"tp={metrics['tp']} fp={metrics['fp']} fn={metrics['fn']} tn={metrics['tn']} "
        f"errors={len(metrics['errors'])}"
    )


def _marker(metrics: dict[str, Any], mode: str) -> str:
    return METRIC_MARKER.format(content=f"mode={mode} {_numbers(metrics)}")


def _previous_run(path: Path) -> tuple[str, str] | None:
    """Return (mode, mode-independent numbers) from the previous results.md."""
    if not path.is_file():
        return None
    match = re.search(
        r"<!-- splitbrain-metrics mode=(\S+) (.*?) -->", path.read_text(encoding="utf-8")
    )
    return (match.group(1), match.group(2)) if match else None


def _same_numbers(previous: tuple[str, str] | None, metrics: dict[str, Any], mode: str) -> bool:
    return previous is not None and previous[0] != mode and previous[1] == _numbers(metrics)


def _console_matrix(metrics: dict[str, Any]) -> list[str]:
    matrix = metrics["matrix"]
    lines = ["Confusion matrix (rows = label, columns = predicted):"]
    header = f"{'':<15}" + "".join(f"{label:>15}" for label in LABELS)
    lines.append(header)
    for label in LABELS:
        lines.append(
            f"{label:<15}" + "".join(f"{matrix[(label, predicted)]:>15}" for predicted in LABELS)
        )
    return lines


def print_report(metrics: dict[str, Any], results: list[PairResult]) -> None:
    print(
        f"contradiction: precision={metrics['precision']:.3f} "
        f"recall={metrics['recall']:.3f} f1={metrics['f1']:.3f}"
    )
    print(
        f"TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} TN={metrics['tn']} "
        f"total={metrics['total']}"
    )
    for line in _console_matrix(metrics):
        print(line)
    print(f"Errors ({len(metrics['errors'])}):")
    if not metrics["errors"]:
        print("  none")
    for error in metrics["errors"]:
        confidence = f" confidence={error.confidence:.2f}" if error.confidence is not None else ""
        print(
            f"  {error.id} label={error.label} predicted={error.predicted} "
            f"stage={error.stage}{confidence}"
        )
        print(f"    reason: {error.reason}")
        print(f"    note: {error.note}")


def _cassette_counts(root: Path) -> dict[str, int]:
    return {
        task: len(list((root / task).glob("*.json"))) if (root / task).is_dir() else 0
        for task in ("extract", "classify")
    }


def _cassette_model(root: Path) -> str | None:
    for task in ("extract", "classify"):
        folder = root / task
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json"))[:1]:
            import json

            record = json.loads(path.read_text(encoding="utf-8"))
            return str(record.get("model", "unknown"))
    return None


def render_markdown(
    metrics: dict[str, Any],
    *,
    settings: LLMSettings,
    pairs: list[EvalPair],
    cassette_counts: dict[str, int],
    previous_mode: str | None,
    identical: bool,
    marker: str,
) -> str:
    label_counts = ", ".join(f"{label}={metrics['labels'].get(label, 0)}" for label in LABELS)
    lines = [
        "# Splitbrain — brain evaluation",
        "",
        f"- Run (UTC): {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- LLM mode: `{settings.mode}`",
        f"- Model: `{settings.model}`",
        f"- Base URL: `{settings.base_url}`",
        f"- Cassette model: `{_cassette_model(settings.cassettes_dir) or 'n/a'}`",
        f"- Dataset: `eval/dataset.jsonl` — {len(pairs)} pairs ({label_counts})",
        f"- Cassettes: extract={cassette_counts['extract']}, "
        f"classify={cassette_counts['classify']}",
        "- Pipeline: prefilter -> extraction -> matching -> classification -> candidate "
        "(threshold 0.7), identical to the Sentinel.",
        "",
        "## Metrics for `contradiction`",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| precision | {metrics['precision']:.3f} |",
        f"| recall | {metrics['recall']:.3f} |",
        f"| F1 | {metrics['f1']:.3f} |",
        f"| TP / FP / FN / TN | {metrics['tp']} / {metrics['fp']} / {metrics['fn']} / "
        f"{metrics['tn']} |",
        "",
        "## Confusion matrix",
        "",
        "| label \\ predicted | " + " | ".join(LABELS) + " |",
        "| --- | " + " | ".join("---" for _ in LABELS) + " |",
    ]
    matrix = metrics["matrix"]
    for label in LABELS:
        cells = " | ".join(str(matrix[(label, predicted)]) for predicted in LABELS)
        lines.append(f"| {label} | {cells} |")
    lines += ["", f"## Errors ({len(metrics['errors'])})", ""]
    if not metrics["errors"]:
        lines.append("None.")
    for error in metrics["errors"]:
        pair = next(item for item in pairs if item.id == error.id)
        confidence = f", confidence={error.confidence:.2f}" if error.confidence is not None else ""
        lines += [
            f"### {error.id} — label `{error.label}`, predicted `{error.predicted}`",
            "",
            f"- Stage: `{error.stage}`{confidence}",
            f"- Reason: {error.reason}",
            f"- Note: {error.note}",
            f"- A (#{pair.a.room}, {pair.a.author}): {pair.a.text}",
            f"- B (#{pair.b.room}, {pair.b.author}): {pair.b.text}",
            "",
        ]
    if identical and previous_mode:
        lines += [
            "## Record / replay",
            "",
            f"Verified: the previous `{previous_mode}` run and this `{settings.mode}` run "
            "produced identical metrics. Replay used the committed cassettes and made no "
            "network calls.",
            "",
        ]
    lines += [marker, ""]
    return "\n".join(lines)


async def run(mode: str | None = None) -> dict[str, Any]:
    settings = LLMSettings.load(mode=resolve_mode(mode))
    pairs = load_dataset(settings.eval_dir / "dataset.jsonl")
    print(f"splitbrain eval — {len(pairs)} pairs from eval/dataset.jsonl")
    print(f"LLM: mode={settings.mode} | model={settings.model} | base_url={settings.base_url}")
    if settings.mode == "replay":
        print("[DEGRADED] replay: reading recorded responses only, no network calls.")

    cassettes = CassetteStore(settings.cassettes_dir, model=settings.model, mode=settings.mode)
    llm = LLMClient(settings, cassettes)
    brain = Brain(llm)
    results: list[PairResult] = []
    try:
        for index, pair in enumerate(pairs, start=1):
            result = await brain.analyze_pair(pair)
            results.append(result)
            mark = "ok" if result.predicted == result.label else "ERROR"
            print(
                f"[{index:02d}/{len(pairs)}] {result.id} predicted={result.predicted} "
                f"label={result.label} {mark}"
            )
    finally:
        await llm.aclose()

    metrics = compute_metrics(results)
    print()
    print_report(metrics, results)

    output = settings.eval_dir / "results.md"
    previous = _previous_run(output)
    identical = _same_numbers(previous, metrics, settings.mode)
    previous_mode = previous[0] if previous else None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_markdown(
            metrics,
            settings=settings,
            pairs=pairs,
            cassette_counts=_cassette_counts(settings.cassettes_dir),
            previous_mode=previous_mode,
            identical=identical,
            marker=_marker(metrics, settings.mode),
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {output.relative_to(settings.eval_dir.parent)}")
    return metrics
