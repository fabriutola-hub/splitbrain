# Classifier guard validation

The implementation was frozen in `b81ace4` before the three live runs. Development
used v2 and its existing reports, including its previously reserved compatible
examples. All of v2 is therefore development data for this change; the runs below
do not establish generalization to unseen contradictions. Dataset labels and
ordering stayed unchanged.

The required README read exposed its pre-existing high-level summary of the
blind evaluation. No blind dataset, blind dataset README, or blind result report
was opened, and no blind examples were used to design the rules. An audit hook
blocked blind evaluation file reads while running the unit suite.

## Implementation

- `src/splitbrain/core/classifier.py`, `Classifier.classify`: classify normally,
  preserving the existing prompts, semantic keys and raw model cassette; consult
  the guard only when the model returns `contradiction`.
- `src/splitbrain/core/classifier_guard.py`, `guard_classification`: require the
  same extracted subject and preserve human decision records. A revision requires
  known, strictly increasing timestamps, overlapping scopes, and an explicit
  revision header. It must identify a self-correction, name the originating team,
  or explicitly withdraw a concrete old value from an internal plan. A revision
  from another person cannot silently undo an explicit customer promise or
  signed contract.
- `_scoped_exception`: require affirmative, explicit approval/signing of an
  exception, a concrete scope mentioned in the same sentence, and an equal or
  narrower scope than the general rule. Negated authorization, tentative
  requests, revocation, expiry, a no-exceptions policy and universal exceptions
  defer to the model. The guard accepts reported authorization as chat data; it
  does not authenticate the author or verify a signed exception independently.
- The grace-period example has no deterministic exclusion: a waiver after the
  announced effective date can still be a substantive disagreement. The model
  retains responsibility for it.

These are deliberately bounded English/Spanish patterns. They do not resolve
every implicit promise, attribution, temporal relationship, or natural-language
scope. An explicit self-correction can be relayed under another author in a
different room, but is insufficient to cancel someone else's customer promise.
The guard does not change extraction, matching, candidate confidence thresholds,
recorded human decisions, or the public demo phrases.

## Independent unit examples

`tests/test_classifier_guard.py` adds 56 cases using newly written archive-export
examples, plus the required real SSO demo regression:

- `test_explicit_self_correction_can_be_relayed_to_another_room`: four English
  and Spanish own-note corrections.
- `test_named_originating_team_can_revise_its_internal_note`: three source-team
  revisions, including bilingual team attribution.
- `test_internal_plan_revision_requires_explicit_withdrawal_of_the_old_value`:
  one internal date revision checked in both argument orders.
- `test_ambiguous_or_tentative_internal_changes_defer_to_model`: seven unrelated
  withdrawals, previews, proposals, questions and conditional changes.
- `test_another_team_revision_does_not_undo_a_customer_promise`: five explicit
  promises or contractual commitments.
- `test_same_author_can_explicitly_correct_their_own_customer_promise`.
- `test_revision_needs_a_known_newer_message`: four missing, tied or reversed
  timestamp cases.
- `test_authorized_scoped_exceptions_can_coexist_with_general_rule`: five
  approved/signed English/Spanish cases checked in both argument orders.
- `test_unapproved_unbounded_or_inapplicable_exceptions_defer`: fifteen negative
  cases, including unrelated authorization in another sentence.
- `test_policy_disputing_an_exception_still_needs_classification`: two explicit
  denials/revocations.
- `test_grace_period_alone_does_not_establish_compatibility`.
- `test_guard_preserves_scope_subject_and_human_decision_boundaries`: four
  scope, subject and persisted-decision boundaries.
- `test_classifier_guards_model_false_alarm_without_rewriting_raw_cassette`.
- `test_classifier_preserves_model_non_contradiction`.
- `test_demo_sso_pair_remains_a_contradiction_without_network`: the unchanged
  seed texts and committed extraction/classification cassettes, zero model calls.
- `test_sso_with_an_explicit_engineering_update_still_conflicts`: a fake-model
  contradiction stays a contradiction even with an explicit revision header.

## Replay and scenarios

Before and after the implementation, `uv run splitbrain eval` printed:

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

Comparing all console predictions by pair ID printed:

```text
Original replay: 44/44 pair predictions unchanged.
Changed predictions: []
```

There are no changed pair predictions to list. The existing errors remain c05,
c10 and n21. The generated `eval/results.md` was restored because only its run
metadata/record-replay formatting changed.

A keyless replay of the Sentinel with the existing recording `Sink` printed:

```text
[DEGRADED] keyless replay with a fake Switch sink; no stack or model calls
[REPLAY] scenario sso          messages=4 candidates=1 reminders=0 llm_calls=0
[REPLAY] scenario sso-followup messages=2 candidates=0 reminders=1 llm_calls=0
[REPLAY] scenario refunds      messages=3 candidates=1 reminders=0 llm_calls=0
[REPLAY] scenario hackathon    messages=2 candidates=1 reminders=0 llm_calls=0
[REPLAY] scenario near-misses  messages=7 candidates=0 reminders=0 llm_calls=0
```

No cassette was added, overwritten or deleted; no new semantic key was needed.
`record --missing` was therefore unnecessary. The scoped status printed:

```text
On branch classifier-guard
nothing to commit, working tree clean
```

## Unit-suite blind-file constraint

The final lint and formatting checks printed:

```text
uv run ruff check .
All checks passed!

uv run ruff format --check .
115 files already formatted
```

The exact requested command, with a local Python audit hook preventing blind
file reads, initially printed:

```text
uv run pytest -m "not integration" -q
FAILED tests/test_eval_v3.py::test_dataset_v3_has_unique_ids_and_expected_label_counts
PermissionError: Blind evaluation files are blocked for this task
1 failed, 667 passed, 5 deselected in 11.01s
```

The hook raised before the blind file could be opened. The failing test checks
the blind dataset itself; changing the implementation cannot satisfy it while
also honoring the prohibition on opening that file. No existing test was edited.
After the last four boundary cases were added, running all remaining unit tests
with the same read protection printed:

```text
uv run pytest -m "not integration" -q --deselect=tests/test_eval_v3.py::test_dataset_v3_has_unique_ids_and_expected_label_counts
671 passed, 6 deselected in 9.56s
```

Five deselections are integration tests; one is the blind-data contract test.
The exact unrestricted full-suite criterion remains for the orchestrator, who
is allowed to read the blind data. Pytest temporary directories were inside the
ignored worktree-local `.splitbrain/classifier-guard/` folder.

## Three frozen-code live runs

Each run used exactly
`uv run splitbrain eval --dataset eval/dataset-v2.jsonl --mode live` and exited 0.
The commands ran sequentially, using the same model/endpoint as the earlier v2
runs, without changing rules after inspecting a run. Actual results:

| run | precision | recall | F1 | TP / FP / FN / TN |
| --- | --- | --- | --- | --- |
| 1 | 1.000 | 0.857 | 0.923 | 30 / 0 / 5 / 65 |
| 2 | 1.000 | 0.857 | 0.923 | 30 / 0 / 5 / 65 |
| 3 | 0.968 | 0.857 | 0.909 | 30 / 1 / 5 / 64 |
| **Mean** | **0.989** | **0.857** | **0.918** | 30.0 / 0.3 / 5.0 / 64.7 |

Relative to the post-prefilter runs, mean precision rises from 0.849 to 0.989,
recall stays 0.857 and F1 rises from 0.853 to 0.918. The requested precision
>= 0.92 and recall >= 0.83 goal is met on v2 development data.

False alarms v042, v044, v049, v060 and v070 are absent in all three runs. The
first three are now `update` in every run; v070 is `compatible` in every run.
v060 is `compatible` in runs 1/2 but `unrelated` at classification in run 3:
its false alarm disappears while its four-label error remains in that run.
No previously unseen false-positive ID appears. v065 remains a false alarm in
run 3; it is rejected by matching in runs 1/2. Those matching-stage absences
must not be credited to the guard, and no grace-period rule was added afterward.

All runs retain the same five false negatives: v007/v008/v021 at prefiltering,
v020 at matching, and v032 at classification. The guard does not fix them.
Four-label errors are 21, 20 and 22 (mean accuracy 0.790); the contradiction
metrics alone do not mean every compatible/update pair is classified correctly.

The third phase, **After classifier guard**, is appended to
[`results-v2-live.md`](results-v2-live.md). Historical prose, tables and every
error were retained; the six previous serialized records are unchanged and
stored together with the three new records. Reconstructing every aggregate
count, metric and confusion-matrix cell with
`uv run python scripts/summarize_eval_splits.py --skip-runs 6` exited 0 and
printed the same metrics. Its old development/reserve ID partition is only a
historical grouping now: the guard used examples from both halves.

## Live-stack follow-up

The orchestrator should run the unchanged SSO, followup, refunds, hackathon and
near-misses flows on the shared stack, plus the existing recovery checks. Verify
one SSO conflict room, zero near-miss conflicts, one followup reminder with no new
room, consent `yes`, the unchanged `decision:` text, `confirm` / `Confirmed,
thanks!`, Arbiter takeover and correction delivery after a Sentinel restart.
The fake-sink checks above do not verify Switch transport, permissions or crash
recovery. No stack command or integration test was run in this worktree.
