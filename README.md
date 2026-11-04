# Splitbrain — agents on Switch that resolve contradictions between teams before they reach a customer.

## One-command demo (M7)

```bash
uv run splitbrain demo --auto-decide          # clean stack + bootstrap + 4 agents + seed + summary
uv run splitbrain demo --auto-decide --offline # replay cassettes + fixture evidence, no keys/network
uv run splitbrain demo --scenario refunds      # or hackathon; without --auto-decide it waits for people
uv run splitbrain record                      # refresh eval + all four scenario cassettes (needs an API key)
```

`demo` starts from a **clean state**: it runs `down --wipe && up && bootstrap` (so the
Sentinel's SQLite store can never pair a new message with an old active claim).
`--keep` reuses the stack but still resets `.splitbrain/sentinel.db`. It launches
`sentinel`, `arbiter`, `arbiter-b` and `verifier` as child processes with prefixed,
coloured logs; Ctrl+C stops all of them. The final summary lists the rooms, the
conflict id, the decision, the corrected threads and the Mattermost URLs/logins
for `maria` and `tomas`. Without `--auto-decide` it prints the exact two lines
María and Tomás must write in the conflict room and waits for them.

Scenarios: `sso` (hero), `refunds` (old $500 policy vs the new $250 threshold,
issue #5 of the demo repo), `hackathon` (the closing beat: the two public
announcement pages disagree on 20 vs 10 pull requests) and `near-misses` (no
alert). A bare `uv run splitbrain seed <scenario>` refuses to run when the
Sentinel still holds active claims for that scenario's rooms, with the exact
cleanup commands in the error.

**Hackathon evidence is explicit, not invented.** The demo roadmap repo has no
issue about the prize pages, so GitHub evidence would honestly be "none" and the
Arbiter would discard the case. `seed/scenario_evidence.json` is a committed,
clearly labelled scenario fixture holding paraphrases of the *two public
announcement pages* themselves. It is enabled only by
`SPLITBRAIN_SCENARIO_EVIDENCE=hackathon` (which `demo --scenario hackathon`
sets), it prints a `[DEGRADED]` banner, and its items use
`scenario-fixture:` identifiers instead of invented URLs. It is never presented
as GitHub data. Running `seed hackathon` by hand without that variable produces
no evidence and no conflict room, by design.

Briefs and decision records show hours with an explicit zone (`Nov 4 12:49 UTC`).
Set `SPLITBRAIN_TZ=America/Caracas` for local hours (`Nov 4 08:49 UTC-04:00`);
an unknown zone fails at startup. `tzdata` is a dependency so this also works on
Windows, which has no system IANA database.

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
- **GitHub fixture** (`SPLITBRAIN_EVIDENCE_MODE=fixture`, also `--offline`): banner
  `[DEGRADED] EVIDENCE: fixture (recorded GitHub data, no network)`. The Verifier reads
  `seed/github_fixture.json`, captured from the public demo repo with
  `uv run python scripts/record_github_fixture.py`.
- **Live evidence** (default, `SPLITBRAIN_EVIDENCE_MODE=live`): banner
  `EVIDENCE: live (GitHub REST, <repo>)`. The repo URL comes from the GitHub
  reference attached to `splitbrain-ops`. A network error fails with a clear
  message; it never falls back to the fixture silently. `GITHUB_TOKEN` is used
  when set.

- **Scenario fixture** (`SPLITBRAIN_SCENARIO_EVIDENCE=hackathon`): banner
  `[DEGRADED] EVIDENCE: scenario fixture 'hackathon' (...); not GitHub data`.
  See "One-command demo" above for why it exists and what it contains.
- **Replay in the demo**: with no `SPLITBRAIN_LLM_API_KEY`, `demo` forces
  `SPLITBRAIN_LLM_MODE=replay` for every child agent; `--offline` forces both
  replay and fixture evidence. Every degraded mode prints its `[DEGRADED]` line
  at startup **and again in the final demo summary**.

Both replay and fixture are declared here and printed at startup, so a demo or a
clone can run without keys or internet without anyone mistaking recorded data for
a live answer.
