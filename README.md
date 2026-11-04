# Splitbrain — agents on Switch that resolve contradictions between teams before they reach a customer.

## Evaluation (M3, "the brain")

`uv run splitbrain eval` runs the same prefilter → extraction → matching →
classification → candidate path the Sentinel will use, over the 44 labeled pairs in
`eval/dataset.jsonl` (18 contradictions, 26 near-misses and other non-conflicts).

| metric | contradiction |
| --- | --- |
| precision | 1.000 |
| recall | 0.889 |
| F1 | 0.941 |

Full confusion matrix and every error with its reason: `eval/results.md`.

The command is offline by default: it replays the committed semantic cassettes in
`cassettes/` (each one records the model that produced it). To refresh them, put
`SPLITBRAIN_LLM_API_KEY` in the gitignored `.env.local` and run
`SPLITBRAIN_LLM_MODE=record uv run splitbrain eval`. A replay with no cassette
raises `ReplayMiss` with the exact input and the command to fix it. Record and
replay produce identical metrics without any network call in replay.
