# Prefilter validation

The prefilter and its tests were frozen in `7ddd17a`; the four missing extraction
cassettes were committed in `b117934` before opening the reserve pairs or detailed
errors. All work and commands ran in the `prefilter-general` worktree. No dataset
labels, extraction prompts, matching rules, or classification rules changed.

Development used only IDs v001-v050. The initial full README read unintentionally
exposed the pre-existing one-line summaries of reserve errors v060 and v070. Those
summaries were not used to design the rules; this is a disclosed limitation of
the information barrier. The reserve pairs and detailed report were first opened
after the code and cassettes were committed. The prefilter was not changed after
that point.

The prescribed ID split is not stratified: development has all 35 contradictions
and 15 updates, while reserve has 25 compatible and 25 unrelated pairs. Reserve
cannot establish recall on new contradictions. False positives, specificity, and
four-label accuracy are reported for it instead. Development is no longer unseen
to the prefilter.

## Implementation and tests

`src/splitbrain/core/prefilter.py` uses Unicode-normalized text, open-ended
number/unit pairs, symbols and currencies, percentages without a trailing word
boundary, written quantities, numeric ranges, inflected commitment verbs,
obligations, negations, and contextual relative deadlines. It still applies the
original author, platform, internal-room, and five-word guards before inspecting
the text. It is deterministic and makes no model calls.

A local timing measurement (not a production benchmark) printed:

```text
Model-free prefilter timing: 200 fixed messages x 100 passes x 3 repeats
Seconds per 20,000 calls: 0.467750, 0.444062, 0.444151
Median per message: 22.208 us (local measurement, not a production benchmark)
```

All 32 original prefilter cases retain their expectations. The 58 independent
new cases in `tests/test_prefilter.py` are:

- `test_open_ended_quantities_are_kept`: 13 quantities, including unfamiliar
  units, attached units, Unicode currencies, percentages, ranges, and Spanish.
- `test_commitment_inflections_and_obligations_are_kept`: 16 cases for English
  and Spanish inflections, contracted futures, obligations, and negations.
- `test_relative_deadlines_are_kept`: 7 contextual deadlines in both languages.
- `test_chatter_and_short_messages_still_drop`: 22 greetings, thanks, lunch
  invitations, empty questions, non-verb lookalikes, punctuation, and short replies.

Before opening reserve, the unit suite excluding its two dataset-reading tests
printed `596 passed, 7 deselected in 10.90s`. The subsequent full allowed suite
printed:

```text
uv run pytest -m "not integration" -q
598 passed, 5 deselected in 10.47s
```

The pytest temporary directories were placed under the ignored
`.splitbrain/prefilter` through `PYTEST_ADDOPTS`. No integration tests or stack
commands were run.

## Original 44-pair replay

Before and after the change, `uv run splitbrain eval` printed:

```text
contradiction: precision=1.000 recall=0.889 f1=0.941
TP=16 FP=0 FN=2 TN=26 total=44
Confusion matrix (rows = label, columns = predicted):
                 contradiction         update     compatible      unrelated
contradiction               16              0              0              2
update                       0              4              0              0
compatible                   0              0              7              1
unrelated                    0              0              0             14
```

An assertion comparing the 44 console predictions printed:

```text
Original replay: 44/44 pair predictions unchanged.
```

The unchanged errors are c05 (the classifier treats the global and customer SLA
as different scopes), c10 (the same issue for payment terms), and n21 (the
matcher treats beta and general availability as different subjects). There is
no recall/F1 change to attribute to individual pairs. The generated
`eval/results.md` was restored because its predictions and metrics did not
change; current cassette counts are recorded below.

## Scenarios and cassette additions

`uv run splitbrain record --missing` was run before changing any code. It printed:

```text
[RECORD] scenario sso          messages=4 candidates=1
[RECORD] scenario sso-followup messages=2 candidates=0
[RECORD] scenario refunds      messages=3 candidates=1
[RECORD] scenario hackathon    messages=2 candidates=1
[RECORD] scenario near-misses  messages=7 candidates=0
[RECORD] cassettes: extract 97 -> 97 (+0), classify 37 -> 37 (+0)
```

The same command after the change printed:

```text
[RECORD] scenario sso          messages=4 candidates=1
[RECORD] scenario sso-followup messages=2 candidates=0
[RECORD] scenario refunds      messages=3 candidates=1
[RECORD] scenario hackathon    messages=2 candidates=1
[RECORD] scenario near-misses  messages=7 candidates=0
[RECORD] cassettes: extract 97 -> 101 (+4), classify 37 -> 37 (+0)
```

All four additions are extraction cassettes for original evaluation sides that
now reach the model: n04.a and n20.a (obligations), plus n04.b and n20.b (partners
that already had signals but were previously skipped because side a was
filtered). The pair predictions remain unrelated. No scenario cassette was
missing, and no existing cassette was modified or deleted. No v2 cassette was
recorded.

A separate keyless replay ran the same Sentinel scenario pipeline with a fake
Switch sink and explicit `api_key=""`. Its real output was:

```text
[DEGRADED] keyless replay with a fake Switch sink; no stack or model calls
[REPLAY] scenario sso          messages=4 candidates=1 reminders=0 llm_calls=0
[REPLAY] scenario sso-followup messages=2 candidates=0 reminders=1 llm_calls=0
[REPLAY] scenario refunds      messages=3 candidates=1 reminders=0 llm_calls=0
[REPLAY] scenario hackathon    messages=2 candidates=1 reminders=0 llm_calls=0
[REPLAY] scenario near-misses  messages=7 candidates=0 reminders=0 llm_calls=0
```

After the cassette additions were committed, the scoped status printed:

```text
git status cassettes/
On branch prefilter-general
nothing to commit, working tree clean
```

## Live-stack follow-up

The orchestrator still needs to run keyless sso, followup, refunds, hackathon,
near-misses, and recovery against the real stack. In particular, check zero
near-miss candidates, a single followup reminder with no new conflict room, the
unchanged proposal/confirmation/consent phrases, Arbiter takeover, and correction
delivery after a Sentinel restart. The fake-sink results above do not verify
transport, permissions, or recovery on Switch.

## Three live runs and split metrics

Each new run used exactly `uv run splitbrain eval --dataset eval/dataset-v2.jsonl --mode live` and exited 0. Runs were sequential; the prefilter stayed frozen.

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T19:48:53+00:00 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 25 | 154 | 294.81s | 1.557s | 248852 / 18284 / 267136 |
| 2 | 2026-11-06T19:53:49+00:00 | 0.833 | 0.857 | 0.845 | 30 / 6 / 5 / 59 | 24 | 155 | 404.84s | 2.256s | 250786 / 18258 / 269044 |
| 3 | 2026-11-06T20:00:35+00:00 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 24 | 154 | 323.50s | 1.744s | 248862 / 18239 / 267101 |
| **Mean** | — | **0.849** | **0.857** | **0.853** | 30.0 / 5.3 / 5.0 / 59.7 | 24.3 | 154.3 | 341.05s | 1.853s | 249500 / 18260 / 267760 |

| run | split | N / positives | precision | recall | F1 | TP / FP / FN / TN | label errors | label accuracy | specificity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | all | 100 / 35 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 25 | 0.750 | 0.923 |
| 1 | development | 50 / 35 | 0.909 | 0.857 | 0.882 | 30 / 3 / 5 / 12 | 11 | 0.780 | 0.800 |
| 1 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 2 / 0 / 48 | 14 | 0.720 | 0.960 |
| 2 | all | 100 / 35 | 0.833 | 0.857 | 0.845 | 30 / 6 / 5 / 59 | 24 | 0.760 | 0.908 |
| 2 | development | 50 / 35 | 0.909 | 0.857 | 0.882 | 30 / 3 / 5 / 12 | 11 | 0.780 | 0.800 |
| 2 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 3 / 0 / 47 | 13 | 0.740 | 0.940 |
| 3 | all | 100 / 35 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 24 | 0.760 | 0.923 |
| 3 | development | 50 / 35 | 0.909 | 0.857 | 0.882 | 30 / 3 / 5 / 12 | 11 | 0.780 | 0.800 |
| 3 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 2 / 0 / 48 | 13 | 0.740 | 0.960 |
| **Mean** | **all** | 100 / 35 | 0.849 | 0.857 | 0.853 | 30.0 / 5.3 / 5.0 / 59.7 | 24.3 | 0.757 | 0.918 |
| **Mean** | **development** | 50 / 35 | 0.909 | 0.857 | 0.882 | 30.0 / 3.0 / 5.0 / 12.0 | 11.0 | 0.780 | 0.800 |
| **Mean** | **reserve** | 50 / 0 | 0.000 | n/a | 0.000 | 0.0 / 2.3 / 0.0 / 47.7 | 13.3 | 0.733 | 0.953 |

### Interpretation

The mean live precision changes from **0.927** to
**0.849**, recall from **0.600** to
**0.857**, and F1 from **0.728** to
**0.853**. Recall improves, but the goal of retaining live
precision is **not achieved**: passing more pairs also exposes classifier false
positives. The original 44-pair replay retains precision 1.000, recall 0.889,
and F1 0.941 with every pair prediction unchanged.

Development four-label accuracy changes from 0.520
to 0.780. Reserve accuracy changes from
0.633 to 0.733,
while its mean false-positive count changes from 0.667
to 2.333 per 50 pairs. The reserve accuracy gain is
smaller, and its false-alarm rate worsens. There is **no reserve recall result**
to support a claim of improved recall on unseen contradictions. Remaining
prefilter false negatives in development are v007, v008, and v021; no words were
added after the frozen evaluation to target them or the reserve errors.

## Lint and cassette verification

```text
uv run ruff check .
All checks passed!
uv run ruff format --check .
107 files already formatted
```

Only additions relative to the baseline:

```text
git diff --name-status f43f3e3 HEAD -- cassettes/
A	cassettes/extract/6457718551d256f6822554e18441766b4a650c7757fdf67eb2559f6588f5e83b.json
A	cassettes/extract/c90d0beec399a13a052bb3ad73104c74d26b25790c49195be8e1d38777e9a8fa.json
A	cassettes/extract/d93b620ea21ccbc93e6b77b64705bc5b925d90a66cf039663c534d3769ca99cd.json
A	cassettes/extract/e59bb2fc76d1cec30c499cea6357c2deb018a36405638054dc4f54a0bf866f14.json
```
