# Unseen eval cases (v2)

`dataset-v2.jsonl` holds **100 brand-new labeled pairs** written to answer an external review of the
original evaluation: the 44 pairs in `dataset.jsonl` were all written by us, so they cannot show how
Splitbrain behaves on information it has never seen.

**labels were written before any run and never changed after.** The whole file was authored and
committed before the first v2 evaluation was executed; no label, text, id, `lang` or `tags` value was
adjusted after seeing a result. The errors in `results-v2-live.md` are reported as they came out.

## How it was built

Each line is one pair with the same shape as `dataset.jsonl` (`id`, two sides `a`/`b` with `room`,
`author` and `text`, a `label`, and a human-readable `note`), plus two fields:

- `lang`: `en`, `es`, or `mixed` (one Spanish message and one English message in the same pair).
- `tags`: a non-empty list of short slice labels used to group errors (for example `currency`,
  `units`, `beta-ga`, `authorized-exception`, `relative-date`, `question`, `scope`).

Labels use the same four relations as the original dataset: `contradiction`, `update`, `compatible`,
`unrelated`. They are human judgments about whether the two statements can both be true, not
predictions of what the pipeline will answer.

| | cases |
| --- | --- |
| contradiction | 35 |
| update | 15 |
| compatible | 25 |
| unrelated | 25 |
| **total** | **100** |

Language mix: 70 `en`, 18 `es`, 12 `mixed` — 30 pairs (30 %) are Spanish or cross-language.

### New subject matter

Every customer, product and named concept was invented for this file. None of the entities from
`dataset.jsonl` or the demo scenarios appear: no Acme, Globex, SSO, refund policy, 99.9 % uptime
clause, admin console, mobile app or enterprise trial. The new world includes cold-chain logistics (Kestrel Logistics,
Maremar), meal kits (Boreal Foods, Casa Verde), clinics (Vela Health, Harborview Clinic), a campus
(Piedmont University), a bank (Meridian Bank), hotels (Orchid Hotels), a ferry operator (Solstice
Travel), energy (Nordvik Energi), retail (Tundra Retail, Quanta Retail), freight (Cobalt Freight,
Ferrovia Rail) and a telecom (Sierra Telecom), with products such as PalletScan, FleetLink,
SampleTrack, SmartLocker, NovaPay, GreenRoute, Aurora assistant, siloTemp and DeskPass. Authors and
rooms are new as well, and the two sides of every pair are always in different rooms.

What is deliberately reused is the *shape* of the problem, not the content: contradictions about
prices, dates, capacities and approvals; later messages that supersede earlier ones; statements that
are both true; and statements that should never produce an alert.

### Coverage

| phenomenon | examples in the tags |
| --- | --- |
| questions that assert nothing | `question` (v078, v081, v087, v091, v095, v099) |
| hypotheses and counterfactuals | `hypothetical` (v079, v082, v088, v092, v096, v100) |
| corrections of one's own earlier message | `own-correction` (v036, v037, v040, v041, v044, v045, v048, v050) |
| explicitly superseded plans | `supersedes` (v038, v039, v042, v043, v046, v047, v049) |
| authorized exceptions for one customer or site | `authorized-exception` (v052, v055, v060, v067, v070, v075) |
| beta versus general availability | `beta-ga` (v003, v012, v028, v051, v054, v061, v069, v073) |
| different units and currencies | `currency`, `units` (v001, v002, v005, v018, v019, v029, v031, v032) |
| unit/currency equivalence that must not alert | `equivalence` (v053, v059, v064, v071) |
| relative dates | `relative-date` ("next Friday", "end of quarter", "el próximo viernes", "fin de trimestre") |
| same claim, different customer or region | `scope`, `different-customer`, `different-region` (v076, v077, v080, v083, v085, v089, v090, v094, v097) |

The last two groups are the trap: they look like conflicts but should not alert. An authorized
exception is labeled `compatible` (both statements are true), while a genuinely different customer
or region is labeled `unrelated`.

## Running it

```bash
uv run splitbrain eval --dataset eval/dataset-v2.jsonl --mode live
```

`--dataset` only changes the input and the output file (`eval/results-v2-live.md`); without it the
command behaves exactly as before and writes `eval/results.md`. Live mode calls the model configured
in the gitignored `.env.local`, needs no cassettes and writes none, so `cassettes/` stays untouched.
The published report contains three independent live runs plus their mean, with the same metrics,
confusion matrices, error lists, timings, latency and token usage as `results-live.md`.

No cassettes were recorded for v2 and no replay of v2 was attempted: replay is only defined for the
committed cassette set that belongs to `dataset.jsonl`.
