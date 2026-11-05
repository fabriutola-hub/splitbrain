# Splitbrain — brain evaluation

- Run (UTC): 2026-11-04T13:45:22+00:00
- LLM mode: `replay`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Base URL: `https://api.river.ai/v1`
- Cassette model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Dataset: `eval/dataset.jsonl` — 44 pairs (contradiction=18, update=4, compatible=8, unrelated=14)
- Cassettes: extract=95, classify=35
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.

## Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.889 |
| F1 | 0.941 |
| TP / FP / FN / TN | 16 / 0 / 2 / 26 |

## Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 16 | 0 | 0 | 2 |
| update | 0 | 4 | 0 | 0 |
| compatible | 0 | 0 | 7 | 1 |
| unrelated | 0 | 0 | 0 | 14 |

## Errors (3)

### c05 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.
- Note: global SLA contradicts a signed customer SLA
- A (#sales, maria): We signed Acme at a 99.9% uptime SLA starting in January, that is contractual.
- B (#ops, dana): Ops can only commit to 99.5% uptime for all customers in January.

### c10 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.
- Note: global payment terms vs a customer promise
- A (#finance, sofia): Standard invoice terms are net 30 for all new contracts starting Monday.
- B (#sales, maria): I promised Acme net 60 payment terms in their renewal, it is in the draft.

### n21 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: beta and GA dates are two phases of one mobile release
- A (#marketing, emma): The mobile app beta opens on December 1 for selected customers.
- B (#engineering, owen): The mobile app reaches general availability in Q1 after the December beta.

## Record / replay

Verified: the previous `record` run and this `replay` run produced identical metrics. Replay used the committed cassettes and made no network calls.

<!-- splitbrain-metrics mode=replay p=1.000000 r=0.888889 f1=0.941176 tp=16 fp=0 fn=2 tn=26 errors=3 -->
