"""`splitbrain eval`: run the detection pipeline over the labeled dataset.

This is the exact path the Sentinel uses (Brain.analyze_pair), so the numbers
below describe what the agent will do in a live room.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator

from .config import LLM_MODES, LLMSettings, SplitbrainError, redact
from .core.models import EvalPair
from .core.pipeline import Brain, PairResult
from .llm.cassette import CassetteStore
from .llm.client import LLMCallStats, LLMClient, LLMTransport

LABELS: tuple[str, ...] = ("contradiction", "update", "compatible", "unrelated")
METRIC_MARKER = "<!-- splitbrain-metrics {content} -->"
LIVE_RUNS_PATTERN = re.compile(r"<!-- splitbrain-live-runs (.*?) -->", re.DOTALL)
V2_KEYS = frozenset({"id", "a", "b", "label", "note", "lang", "tags"})


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


class EvalPairV2(EvalPair):
    """An unseen-cases pair: the original contract plus language and slice tags."""

    lang: Literal["en", "es", "mixed"]
    tags: list[str]

    @field_validator("tags")
    @classmethod
    def _tags_are_useful(cls, value: list[str]) -> list[str]:
        if not value or any(not tag.strip() for tag in value):
            raise ValueError("tags must be a non-empty list of non-empty strings")
        return value


def load_dataset_v2(path: Path) -> list[EvalPairV2]:
    if not path.is_file():
        raise SplitbrainError(f"Evaluation dataset is missing: {path}")
    pairs: list[EvalPairV2] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict) or set(raw) != V2_KEYS:
                raise ValueError("expected id, a, b, label, note, lang and tags")
            pairs.append(EvalPairV2.model_validate(raw))
        except ValueError as exc:
            raise SplitbrainError(f"{path}:{number} is not a valid v2 eval pair: {exc}") from exc
    if not pairs:
        raise SplitbrainError(f"Evaluation dataset is empty: {path}")
    if len({pair.id for pair in pairs}) != len(pairs):
        raise SplitbrainError(f"{path}: duplicate pair ids")
    return pairs


def resolve_dataset(settings: LLMSettings, dataset: str | Path | None) -> tuple[Path, str, str]:
    """Return (path, display name, report suffix); None keeps the release defaults."""
    if dataset is None:
        return settings.eval_dir / "dataset.jsonl", "eval/dataset.jsonl", ""
    given = Path(dataset)
    if given.is_absolute():
        source = given
    else:
        rooted = settings.eval_dir.parent / given
        source = rooted if rooted.is_file() else Path.cwd() / given
    try:
        display = source.relative_to(settings.eval_dir.parent).as_posix()
    except ValueError:
        display = given.as_posix()
    suffix = source.stem.removeprefix("dataset")
    if suffix and not suffix.startswith("-"):
        suffix = f"-{suffix}"
    return source, display, suffix


def _dataset_extra_lines(pairs: list[EvalPair]) -> list[str]:
    """Only datasets carrying `lang` get an extra line; release reports stay identical."""
    langs = Counter(str(pair.lang) for pair in pairs if getattr(pair, "lang", None))
    if not langs:
        return []
    mix = ", ".join(f"{lang}={langs[lang]}" for lang in ("en", "es", "mixed") if langs[lang])
    return [f"- Language mix: {mix}"]


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
    dataset_name: str = "eval/dataset.jsonl",
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
        f"- Dataset: `{dataset_name}` — {len(pairs)} pairs ({label_counts})",
        *_dataset_extra_lines(pairs),
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


def build_live_run_record(
    metrics: dict[str, Any],
    *,
    settings: LLMSettings,
    duration_s: float,
    call_stats: LLMCallStats,
    run_utc: str | None = None,
) -> dict[str, Any]:
    timestamp = run_utc or datetime.now(UTC).isoformat(timespec="seconds")
    matrix = {
        f"{label}:{predicted}": int(metrics["matrix"][(label, predicted)])
        for label in LABELS
        for predicted in LABELS
    }
    errors = [
        {
            "id": error.id,
            "label": error.label,
            "predicted": error.predicted,
            "stage": error.stage,
            "confidence": error.confidence,
            "reason": error.reason,
            "note": error.note,
        }
        for error in metrics["errors"]
    ]
    return {
        "run_utc": timestamp,
        "model": settings.model,
        "base_url": settings.base_url,
        "duration_s": round(float(duration_s), 3),
        "llm_calls": int(call_stats.calls),
        "mean_latency_s": round(float(call_stats.mean_latency_s), 4),
        "usage_reported": bool(call_stats.usage_reported),
        "prompt_tokens": int(call_stats.prompt_tokens),
        "completion_tokens": int(call_stats.completion_tokens),
        "total_tokens": int(call_stats.total_tokens),
        "tp": int(metrics["tp"]),
        "fp": int(metrics["fp"]),
        "fn": int(metrics["fn"]),
        "tn": int(metrics["tn"]),
        "precision": float(metrics["precision"]),
        "recall": float(metrics["recall"]),
        "f1": float(metrics["f1"]),
        "matrix": matrix,
        "errors": errors,
    }


def load_live_runs(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    match = LIVE_RUNS_PATTERN.search(path.read_text(encoding="utf-8"))
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except ValueError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _format_tokens_cell(run: dict[str, Any]) -> str:
    if not run.get("usage_reported"):
        return "not returned by API"
    return f"{run['prompt_tokens']} / {run['completion_tokens']} / {run['total_tokens']}"


def render_live_markdown(
    runs: list[dict[str, Any]],
    *,
    settings: LLMSettings,
    pairs: list[EvalPair],
    dataset_name: str = "eval/dataset.jsonl",
) -> str:
    if not runs:
        raise ValueError("render_live_markdown requires at least one run")
    counts = Counter(str(pair.label) for pair in pairs)
    label_counts = ", ".join(f"{label}={counts.get(label, 0)}" for label in LABELS)
    latest = runs[-1]
    n = len(runs)
    mean_precision = sum(float(r["precision"]) for r in runs) / n
    mean_recall = sum(float(r["recall"]) for r in runs) / n
    mean_f1 = sum(float(r["f1"]) for r in runs) / n
    mean_tp = sum(int(r["tp"]) for r in runs) / n
    mean_fp = sum(int(r["fp"]) for r in runs) / n
    mean_fn = sum(int(r["fn"]) for r in runs) / n
    mean_tn = sum(int(r["tn"]) for r in runs) / n
    mean_errors = sum(len(r["errors"]) for r in runs) / n
    mean_calls = sum(int(r["llm_calls"]) for r in runs) / n
    mean_duration = sum(float(r["duration_s"]) for r in runs) / n
    mean_latency = sum(float(r["mean_latency_s"]) for r in runs) / n

    usage_runs = [r for r in runs if r.get("usage_reported")]
    if usage_runs:
        u_count = len(usage_runs)
        mean_prompt = round(sum(int(r["prompt_tokens"]) for r in usage_runs) / u_count)
        mean_completion = round(sum(int(r["completion_tokens"]) for r in usage_runs) / u_count)
        mean_total_tok = round(sum(int(r["total_tokens"]) for r in usage_runs) / u_count)
        mean_tokens_cell = f"{mean_prompt} / {mean_completion} / {mean_total_tok}"
        total_prompt = sum(int(r["prompt_tokens"]) for r in usage_runs)
        total_completion = sum(int(r["completion_tokens"]) for r in usage_runs)
        total_tok = sum(int(r["total_tokens"]) for r in usage_runs)
        token_summary_note = (
            f"- Token usage across {u_count} run(s): input={total_prompt}, "
            f"output={total_completion}, total={total_tok} "
            f"(mean per run: {mean_prompt} in / {mean_completion} out / {mean_total_tok} total; "
            "API dollar costs are not estimated)."
        )
    else:
        mean_tokens_cell = "not returned by API"
        token_summary_note = (
            "- Token usage: the API endpoint did not return input/output token counts "
            "(costs are not estimated)."
        )

    lines = [
        "# Splitbrain — live brain evaluation",
        "",
        f"- Latest run (UTC): {latest['run_utc']}",
        "- LLM mode: `live`",
        f"- Model: `{latest['model']}`",
        f"- Endpoint (Base URL): `{latest['base_url']}`",
        f"- Dataset: `{dataset_name}` — {len(pairs)} pairs ({label_counts})",
        *_dataset_extra_lines(pairs),
        f"- Runs recorded: {n}",
        "- Pipeline: prefilter -> extraction -> matching -> classification -> candidate "
        "(threshold 0.7), identical to the Sentinel.",
        token_summary_note,
        "",
        "## Summary across live runs",
        "",
        "| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | "
        "total time | mean latency / call | tokens (in / out / total) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for idx, run in enumerate(runs, start=1):
        lines.append(
            f"| {idx} | {run['run_utc']} | {run['precision']:.3f} | {run['recall']:.3f} | "
            f"{run['f1']:.3f} | {run['tp']} / {run['fp']} / {run['fn']} / {run['tn']} | "
            f"{len(run['errors'])} | {run['llm_calls']} | {run['duration_s']:.2f}s | "
            f"{run['mean_latency_s']:.3f}s | {_format_tokens_cell(run)} |"
        )
    lines.append(
        f"| **Mean** | — | **{mean_precision:.3f}** | **{mean_recall:.3f}** | "
        f"**{mean_f1:.3f}** | {mean_tp:.1f} / {mean_fp:.1f} / {mean_fn:.1f} / {mean_tn:.1f} | "
        f"{mean_errors:.1f} | {mean_calls:.1f} | {mean_duration:.2f}s | "
        f"{mean_latency:.3f}s | {mean_tokens_cell} |"
    )
    lines.append("")

    pair_by_id = {pair.id: pair for pair in pairs}
    for idx, run in enumerate(runs, start=1):
        if run.get("usage_reported"):
            token_line = (
                f"- Token usage: input={run['prompt_tokens']}, "
                f"output={run['completion_tokens']}, total={run['total_tokens']} "
                "(costs are not estimated)"
            )
        else:
            token_line = "- Token usage: not returned by the API endpoint (costs are not estimated)"
        lines += [
            f"## Run {idx} — {run['run_utc']}",
            "",
            f"- Run (UTC): {run['run_utc']}",
            f"- Model: `{run['model']}`",
            f"- Endpoint (Base URL): `{run['base_url']}`",
            f"- Total run time: {run['duration_s']:.2f}s",
            f"- LLM calls: {run['llm_calls']} (mean latency {run['mean_latency_s']:.3f}s per call)",
            token_line,
            "",
            "### Metrics for `contradiction`",
            "",
            "| metric | value |",
            "| --- | --- |",
            f"| precision | {run['precision']:.3f} |",
            f"| recall | {run['recall']:.3f} |",
            f"| F1 | {run['f1']:.3f} |",
            f"| TP / FP / FN / TN | {run['tp']} / {run['fp']} / {run['fn']} / {run['tn']} |",
            "",
            "### Confusion matrix",
            "",
            "| label \\ predicted | " + " | ".join(LABELS) + " |",
            "| --- | " + " | ".join("---" for _ in LABELS) + " |",
        ]
        matrix = run["matrix"]
        for label in LABELS:
            cells = " | ".join(str(matrix.get(f"{label}:{predicted}", 0)) for predicted in LABELS)
            lines.append(f"| {label} | {cells} |")
        errors = run["errors"]
        lines += ["", f"### Errors ({len(errors)})", ""]
        if not errors:
            lines.append("None.")
            lines.append("")
        for error in errors:
            pair = pair_by_id.get(error["id"])
            confidence = (
                f", confidence={error['confidence']:.2f}"
                if error.get("confidence") is not None
                else ""
            )
            lines += [
                f"#### {error['id']} — label `{error['label']}`, predicted `{error['predicted']}`",
                "",
                f"- Stage: `{error['stage']}`{confidence}",
                f"- Reason: {error['reason']}",
                f"- Note: {error['note']}",
            ]
            if pair is not None:
                lines += [
                    f"- A (#{pair.a.room}, {pair.a.author}): {pair.a.text}",
                    f"- B (#{pair.b.room}, {pair.b.author}): {pair.b.text}",
                ]
            lines.append("")

    serialized = json.dumps(runs, separators=(",", ":"))
    lines += [f"<!-- splitbrain-live-runs {serialized} -->", ""]
    return redact("\n".join(lines), (settings.api_key,))


async def run(
    mode: str | None = None,
    *,
    dataset: str | Path | None = None,
    overwrite: bool = True,
    write_report: bool = True,
    reset_live: bool = False,
    transport: LLMTransport | None = None,
) -> dict[str, Any]:
    settings = LLMSettings.load(mode=resolve_mode(mode))
    source, display, suffix = resolve_dataset(settings, dataset)
    release_dataset = settings.eval_dir / "dataset.jsonl"
    if dataset is None or source.resolve() == release_dataset.resolve():
        # Passing the release dataset explicitly must behave exactly like the default.
        pairs = load_dataset(source)
    else:
        pairs = load_dataset_v2(source)
    print(f"splitbrain eval — {len(pairs)} pairs from {display}")
    print(f"LLM: mode={settings.mode} | model={settings.model} | base_url={settings.base_url}")
    if settings.mode == "replay":
        print("[DEGRADED] replay: reading recorded responses only, no network calls.")

    cassettes = CassetteStore(
        settings.cassettes_dir,
        model=settings.model,
        mode=settings.mode,
        overwrite=overwrite,
    )
    llm = LLMClient(settings, cassettes, transport=transport)
    brain = Brain(llm)
    results: list[PairResult] = []
    run_utc = datetime.now(UTC).isoformat(timespec="seconds")
    started = time.monotonic()
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
    duration_s = time.monotonic() - started
    call_stats = llm.stats()

    metrics = compute_metrics(results)
    metrics["duration_s"] = duration_s
    metrics["llm_calls"] = call_stats.calls
    metrics["mean_latency_s"] = call_stats.mean_latency_s
    metrics["usage_reported"] = call_stats.usage_reported
    metrics["prompt_tokens"] = call_stats.prompt_tokens
    metrics["completion_tokens"] = call_stats.completion_tokens
    metrics["total_tokens"] = call_stats.total_tokens

    print()
    print_report(metrics, results)
    if settings.mode == "live":
        tokens_str = (
            f"in={call_stats.prompt_tokens} out={call_stats.completion_tokens} "
            f"total={call_stats.total_tokens}"
            if call_stats.usage_reported
            else "not reported by API"
        )
        print(
            f"Timing: total={duration_s:.2f}s | calls={call_stats.calls} | "
            f"mean_latency={call_stats.mean_latency_s:.3f}s | tokens: {tokens_str}"
        )

    if write_report:
        if settings.mode == "live":
            output = settings.eval_dir / f"results{suffix}-live.md"
            previous_runs = [] if reset_live else load_live_runs(output)
            current_record = build_live_run_record(
                metrics,
                settings=settings,
                duration_s=duration_s,
                call_stats=call_stats,
                run_utc=run_utc,
            )
            all_runs = [*previous_runs, current_record]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                render_live_markdown(
                    all_runs, settings=settings, pairs=pairs, dataset_name=display
                ),
                encoding="utf-8",
            )
            print(f"\nWrote {output.relative_to(settings.eval_dir.parent)} (run {len(all_runs)})")
        else:
            output = settings.eval_dir / f"results{suffix}.md"
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
                    dataset_name=display,
                ),
                encoding="utf-8",
            )
            print(f"\nWrote {output.relative_to(settings.eval_dir.parent)}")
    return metrics
