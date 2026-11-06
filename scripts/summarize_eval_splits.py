"""Reconstruct per-ID metrics from a live report's complete list of label errors.

Usage: uv run python scripts/summarize_eval_splits.py --skip-runs 3
Correct predictions equal the dataset label; every other prediction is in errors.
The reconstructed overall counts and metrics must match the recorded run.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from splitbrain.core.models import EvalPair
from splitbrain.core.pipeline import PairResult
from splitbrain.evaluation import compute_metrics, load_dataset_v2, load_live_runs


def reconstruct(run: dict[str, Any], pairs: list[EvalPair]) -> list[PairResult]:
    errors = {error["id"]: error for error in run["errors"]}
    if len(errors) != len(run["errors"]) or set(errors) - {pair.id for pair in pairs}:
        raise ValueError("Report contains duplicate or unknown error IDs")
    results = []
    for pair in pairs:
        error = errors.get(pair.id)
        if error and (error["label"] != str(pair.label) or error["predicted"] == str(pair.label)):
            raise ValueError(f"Report error disagrees with dataset: {pair.id}")
        predicted = error["predicted"] if error else str(pair.label)
        results.append(
            PairResult(
                id=pair.id,
                label=str(pair.label),
                predicted=predicted,
                relation=None,
                confidence=None,
                reason="reconstructed from stored label errors",
                stage=error["stage"] if error else "correct",
                candidate=predicted == "contradiction",
                note=pair.note,
            )
        )
    metrics = compute_metrics(results)
    for name in ("tp", "fp", "fn", "tn", "precision", "recall", "f1"):
        if not math.isclose(metrics[name], run[name], abs_tol=1e-9):
            raise ValueError(f"Reconstructed {name} differs from the recorded run")
    if any(metrics["matrix"][key] != run["matrix"][":".join(key)] for key in metrics["matrix"]):
        raise ValueError("Reconstructed confusion matrix differs from the recorded run")
    return results


def summary(results: list[PairResult]) -> dict[str, Any]:
    metrics = compute_metrics(results)
    positives = metrics["tp"] + metrics["fn"]
    negatives = metrics["tn"] + metrics["fp"]
    return {
        "total": len(results),
        "positives": positives,
        "precision": metrics["precision"] if metrics["tp"] + metrics["fp"] else None,
        "recall": metrics["recall"] if positives else None,
        "f1": metrics["f1"] if 2 * metrics["tp"] + metrics["fp"] + metrics["fn"] else None,
        "specificity": metrics["tn"] / negatives if negatives else None,
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "fn": metrics["fn"],
        "tn": metrics["tn"],
        "errors": len(metrics["errors"]),
        "accuracy": (len(results) - len(metrics["errors"])) / len(results),
    }


def metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def split_table(runs: list[dict[str, Any]], pairs: list[EvalPair], *, skip: int = 0) -> str:
    if {pair.id for pair in pairs} != {f"v{i:03d}" for i in range(1, 101)}:
        raise ValueError("Expected IDs v001-v100 for this development/reserve split")
    groups: dict[str, list[dict[str, Any]]] = {"all": [], "development": [], "reserve": []}
    lines = [
        "| run | split | N / positives | precision | recall | F1 | TP / FP / FN / TN | "
        "label errors | label accuracy | specificity |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, run in enumerate(runs, start=1):
        if index <= skip:
            continue
        results = reconstruct(run, pairs)
        for name in groups:
            subset = [
                result
                for result in results
                if name == "all" or (int(result.id[1:]) <= 50) == (name == "development")
            ]
            row = summary(subset)
            groups[name].append(row)
            lines.append(
                f"| {index} | {name} | {row['total']} / {row['positives']} | "
                + " | ".join(metric(row[key]) for key in ("precision", "recall", "f1"))
                + " | "
                + " / ".join(str(row[key]) for key in ("tp", "fp", "fn", "tn"))
                + f" | {row['errors']} | {metric(row['accuracy'])} | {metric(row['specificity'])} |"
            )
    if not groups["all"]:
        raise ValueError("No runs selected")
    for name, rows in groups.items():
        means = {
            key: sum(row[key] for row in rows) / len(rows)
            if all(row[key] is not None for row in rows)
            else None
            for key in rows[0]
        }
        lines.append(
            f"| **Mean** | **{name}** | {int(means['total'])} / {int(means['positives'])} | "
            + " | ".join(metric(means[key]) for key in ("precision", "recall", "f1"))
            + " | "
            + " / ".join(f"{means[key]:.1f}" for key in ("tp", "fp", "fn", "tn"))
            + f" | {means['errors']:.1f} | {metric(means['accuracy'])} | "
            + f"{metric(means['specificity'])} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("eval/dataset-v2.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("eval/results-v2-live.md"))
    parser.add_argument("--skip-runs", type=int, default=0)
    args = parser.parse_args()
    print(
        split_table(load_live_runs(args.report), load_dataset_v2(args.dataset), skip=args.skip_runs)
    )
    print(
        "\nn/a: zero denominator; reserve recall cannot be measured without actual contradictions."
    )


if __name__ == "__main__":
    main()
