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

## Degraded modes (always announced on stdout)

- **Model replay** (`SPLITBRAIN_LLM_MODE=replay`, the default with no API key):
  banner `[DEGRADED] replay: recorded model responses only, no network calls.`
  No internet is used; a missing cassette raises `ReplayMiss`. `record` mode
  re-records the semantic cassettes under `cassettes/`.
- **GitHub fixture** (`SPLITBRAIN_EVIDENCE_MODE=fixture`): banner
  `EVIDENCE: fixture (recorded GitHub data)`. The Verifier reads
  `seed/github_fixture.json`, captured from the public demo repo with
  `uv run python scripts/record_github_fixture.py`.
- **Live evidence** (default, `SPLITBRAIN_EVIDENCE_MODE=live`): banner
  `EVIDENCE: live (GitHub REST, <repo>)`. The repo URL comes from the GitHub
  reference attached to `splitbrain-ops`. A network error fails with a clear
  message; it never falls back to the fixture silently. `GITHUB_TOKEN` is used
  when set.

Both replay and fixture are declared here and printed at startup, so a demo or a
clone can run without keys or internet without anyone mistaking recorded data for
a live answer.
