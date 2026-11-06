# Splitbrain — live brain evaluation

- Latest run (UTC): 2026-11-06T07:10:45+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset.jsonl` — 44 pairs (contradiction=18, update=4, compatible=8, unrelated=14)
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=334583, output=24243, total=358826 (mean per run: 111528 in / 8081 out / 119609 total; API dollar costs are not estimated).

## Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T07:03:41+00:00 | 1.000 | 0.833 | 0.909 | 15 / 0 / 3 / 26 | 4 | 69 | 160.75s | 1.976s | 111527 / 8034 / 119561 |
| 2 | 2026-11-06T07:06:32+00:00 | 1.000 | 0.833 | 0.909 | 15 / 0 / 3 / 26 | 4 | 69 | 241.20s | 3.142s | 111527 / 8173 / 119700 |
| 3 | 2026-11-06T07:10:45+00:00 | 1.000 | 0.833 | 0.909 | 15 / 0 / 3 / 26 | 4 | 69 | 214.02s | 2.651s | 111529 / 8036 / 119565 |
| **Mean** | — | **1.000** | **0.833** | **0.909** | 15.0 / 0.0 / 3.0 / 26.0 | 4.0 | 69.0 | 205.32s | 2.589s | 111528 / 8081 / 119609 |

## Run 1 — 2026-11-06T07:03:41+00:00

- Run (UTC): 2026-11-06T07:03:41+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 160.75s
- LLM calls: 69 (mean latency 1.976s per call)
- Token usage: input=111527, output=8034, total=119561 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.833 |
| F1 | 0.909 |
| TP / FP / FN / TN | 15 / 0 / 3 / 26 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 15 | 0 | 0 | 3 |
| update | 0 | 4 | 0 | 0 |
| compatible | 0 | 0 | 7 | 1 |
| unrelated | 0 | 0 | 0 | 14 |

### Errors (4)

#### c05 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.
- Note: global SLA contradicts a signed customer SLA
- A (#sales, maria): We signed Acme at a 99.9% uptime SLA starting in January, that is contractual.
- B (#ops, dana): Ops can only commit to 99.5% uptime for all customers in January.

#### c10 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.
- Note: global payment terms vs a customer promise
- A (#finance, sofia): Standard invoice terms are net 30 for all new contracts starting Monday.
- B (#sales, maria): I promised Acme net 60 payment terms in their renewal, it is in the draft.

#### c16 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The finance policy applies company-wide while the support note scopes the change to the support team, so the scopes differ.
- Note: Spanish pair: approval required vs no longer required
- A (#finance, pablo): Confirmé que los reembolsos mayores a 250 USD requieren aprobación del gerente desde hoy.
- B (#support, lucia): Aviso a soporte: los reembolsos ya no requieren aprobación del gerente, pueden aprobarlos directamente.

#### n21 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: beta and GA dates are two phases of one mobile release
- A (#marketing, emma): The mobile app beta opens on December 1 for selected customers.
- B (#engineering, owen): The mobile app reaches general availability in Q1 after the December beta.

## Run 2 — 2026-11-06T07:06:32+00:00

- Run (UTC): 2026-11-06T07:06:32+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 241.20s
- LLM calls: 69 (mean latency 3.142s per call)
- Token usage: input=111527, output=8173, total=119700 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.833 |
| F1 | 0.909 |
| TP / FP / FN / TN | 15 / 0 / 3 / 26 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 15 | 0 | 0 | 3 |
| update | 0 | 4 | 0 | 0 |
| compatible | 0 | 0 | 7 | 1 |
| unrelated | 0 | 0 | 0 | 14 |

### Errors (4)

#### c05 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.
- Note: global SLA contradicts a signed customer SLA
- A (#sales, maria): We signed Acme at a 99.9% uptime SLA starting in January, that is contractual.
- B (#ops, dana): Ops can only commit to 99.5% uptime for all customers in January.

#### c10 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.
- Note: global payment terms vs a customer promise
- A (#finance, sofia): Standard invoice terms are net 30 for all new contracts starting Monday.
- B (#sales, maria): I promised Acme net 60 payment terms in their renewal, it is in the draft.

#### c16 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The finance policy applies company-wide while the support note addresses only the support team's handling, so the scopes differ.
- Note: Spanish pair: approval required vs no longer required
- A (#finance, pablo): Confirmé que los reembolsos mayores a 250 USD requieren aprobación del gerente desde hoy.
- B (#support, lucia): Aviso a soporte: los reembolsos ya no requieren aprobación del gerente, pueden aprobarlos directamente.

#### n21 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: beta and GA dates are two phases of one mobile release
- A (#marketing, emma): The mobile app beta opens on December 1 for selected customers.
- B (#engineering, owen): The mobile app reaches general availability in Q1 after the December beta.

## Run 3 — 2026-11-06T07:10:45+00:00

- Run (UTC): 2026-11-06T07:10:45+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 214.02s
- LLM calls: 69 (mean latency 2.651s per call)
- Token usage: input=111529, output=8036, total=119565 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.833 |
| F1 | 0.909 |
| TP / FP / FN / TN | 15 / 0 / 3 / 26 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 15 | 0 | 0 | 3 |
| update | 0 | 4 | 0 | 0 |
| compatible | 0 | 0 | 7 | 1 |
| unrelated | 0 | 0 | 0 | 14 |

### Errors (4)

#### c05 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.
- Note: global SLA contradicts a signed customer SLA
- A (#sales, maria): We signed Acme at a 99.9% uptime SLA starting in January, that is contractual.
- B (#ops, dana): Ops can only commit to 99.5% uptime for all customers in January.

#### c10 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.
- Note: global payment terms vs a customer promise
- A (#finance, sofia): Standard invoice terms are net 30 for all new contracts starting Monday.
- B (#sales, maria): I promised Acme net 60 payment terms in their renewal, it is in the draft.

#### c16 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The finance policy applies globally while the support note addresses only the support team's own approval scope, so the scopes differ.
- Note: Spanish pair: approval required vs no longer required
- A (#finance, pablo): Confirmé que los reembolsos mayores a 250 USD requieren aprobación del gerente desde hoy.
- B (#support, lucia): Aviso a soporte: los reembolsos ya no requieren aprobación del gerente, pueden aprobarlos directamente.

#### n21 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: beta and GA dates are two phases of one mobile release
- A (#marketing, emma): The mobile app beta opens on December 1 for selected customers.
- B (#engineering, owen): The mobile app reaches general availability in Q1 after the December beta.

<!-- splitbrain-live-runs [{"run_utc":"2026-11-06T07:03:41+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":160.75,"llm_calls":69,"mean_latency_s":1.9758,"usage_reported":true,"prompt_tokens":111527,"completion_tokens":8034,"total_tokens":119561,"tp":15,"fp":0,"fn":3,"tn":26,"precision":1.0,"recall":0.8333333333333334,"f1":0.9090909090909091,"matrix":{"contradiction:contradiction":15,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":3,"update:contradiction":0,"update:update":4,"update:compatible":0,"update:unrelated":0,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":1,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":14},"errors":[{"id":"c05","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.","note":"global SLA contradicts a signed customer SLA"},{"id":"c10","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.","note":"global payment terms vs a customer promise"},{"id":"c16","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The finance policy applies company-wide while the support note scopes the change to the support team, so the scopes differ.","note":"Spanish pair: approval required vs no longer required"},{"id":"n21","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"beta and GA dates are two phases of one mobile release"}]},{"run_utc":"2026-11-06T07:06:32+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":241.203,"llm_calls":69,"mean_latency_s":3.1416,"usage_reported":true,"prompt_tokens":111527,"completion_tokens":8173,"total_tokens":119700,"tp":15,"fp":0,"fn":3,"tn":26,"precision":1.0,"recall":0.8333333333333334,"f1":0.9090909090909091,"matrix":{"contradiction:contradiction":15,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":3,"update:contradiction":0,"update:update":4,"update:compatible":0,"update:unrelated":0,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":1,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":14},"errors":[{"id":"c05","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.","note":"global SLA contradicts a signed customer SLA"},{"id":"c10","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.","note":"global payment terms vs a customer promise"},{"id":"c16","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The finance policy applies company-wide while the support note addresses only the support team's handling, so the scopes differ.","note":"Spanish pair: approval required vs no longer required"},{"id":"n21","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"beta and GA dates are two phases of one mobile release"}]},{"run_utc":"2026-11-06T07:10:45+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":214.016,"llm_calls":69,"mean_latency_s":2.6507,"usage_reported":true,"prompt_tokens":111529,"completion_tokens":8036,"total_tokens":119565,"tp":15,"fp":0,"fn":3,"tn":26,"precision":1.0,"recall":0.8333333333333334,"f1":0.9090909090909091,"matrix":{"contradiction:contradiction":15,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":3,"update:contradiction":0,"update:update":4,"update:compatible":0,"update:unrelated":0,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":1,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":14},"errors":[{"id":"c05","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"Ops states a general 99.5% commitment for all customers while sales cites a specific contractual 99.9% SLA for Acme, so the scopes differ.","note":"global SLA contradicts a signed customer SLA"},{"id":"c10","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The net 30 policy applies to all new contracts while the net 60 commitment is specific to Acme's renewal, so they cover different scopes.","note":"global payment terms vs a customer promise"},{"id":"c16","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The finance policy applies globally while the support note addresses only the support team's own approval scope, so the scopes differ.","note":"Spanish pair: approval required vs no longer required"},{"id":"n21","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"beta and GA dates are two phases of one mobile release"}]}] -->
