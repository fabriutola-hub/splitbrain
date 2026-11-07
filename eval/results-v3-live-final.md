# Splitbrain — live brain evaluation

Configuration: **broader prefilter + classifier guard + new topic matcher**
(`src/splitbrain/core/prefilter.py`, `src/splitbrain/core/classifier_guard.py`,
`src/splitbrain/core/matcher.py`), matching code base `e147233`. This is the final
configuration. Compare the [original prefilter baseline](results-v3-live-before-prefilter.md)
and [broader prefilter only, without guard or new matcher](results-v3-live.md).
All use the same frozen 60-pair v3 dataset and the same model/endpoint.

The final runs below each have 18 TP, 0 FP, 2 FN and 40 TN: precision 1.000,
recall 0.900, F1 0.947, with four label errors. The remaining errors are w023
(a unit-conversion false negative), w057 (a prefiltered contradiction), and
w014/w058 (prefiltered updates). The five compatible pairs rejected by matching
in the prefilter-only report are correct in these final runs. Thus contradiction
metrics are unchanged while label errors fall from nine to four per run.

**Intermediate check: prefilter + guard, original matcher**

Three separate live checks before the matcher change also retained precision
1.000, recall 0.900 and F1 0.947, with eight label errors each. Their summary is
included here for context; the detailed run tables and serialized records below
contain only the three final-configuration runs.

| Check | UTC | Precision | Recall | F1 | Label errors |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T23:32:17+00:00 | 1.000 | 0.900 | 0.947 | 8 |
| 2 | 2026-11-06T23:35:01+00:00 | 1.000 | 0.900 | 0.947 | 8 |
| 3 | 2026-11-06T23:37:47+00:00 | 1.000 | 0.900 | 0.947 | 8 |

**Final configuration runs**

- Latest run (UTC): 2026-11-07T00:37:40+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v3.jsonl` — 60 pairs (contradiction=20, update=10, compatible=15, unrelated=15)
- Language mix: en=42, es=12, mixed=6
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=498621, output=45846, total=544467 (mean per run: 166207 in / 15282 out / 181489 total; API dollar costs are not estimated).

## Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-07T00:23:08+00:00 | 1.000 | 0.900 | 0.947 | 18 / 0 / 2 / 40 | 4 | 98 | 173.42s | 1.345s | 166206 / 15300 / 181506 |
| 2 | 2026-11-07T00:30:33+00:00 | 1.000 | 0.900 | 0.947 | 18 / 0 / 2 / 40 | 4 | 98 | 167.34s | 1.351s | 166195 / 15321 / 181516 |
| 3 | 2026-11-07T00:37:40+00:00 | 1.000 | 0.900 | 0.947 | 18 / 0 / 2 / 40 | 4 | 98 | 163.00s | 1.283s | 166220 / 15225 / 181445 |
| **Mean** | — | **1.000** | **0.900** | **0.947** | 18.0 / 0.0 / 2.0 / 40.0 | 4.0 | 98.0 | 167.92s | 1.327s | 166207 / 15282 / 181489 |

## Run 1 — 2026-11-07T00:23:08+00:00

- Run (UTC): 2026-11-07T00:23:08+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 173.42s
- LLM calls: 98 (mean latency 1.345s per call)
- Token usage: input=166206, output=15300, total=181506 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.900 |
| F1 | 0.947 |
| TP / FP / FN / TN | 18 / 0 / 2 / 40 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 18 | 0 | 1 | 1 |
| update | 0 | 8 | 0 | 2 |
| compatible | 0 | 0 | 15 | 0 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (4)

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: Both claims state the same 12-hour (1,440-minute) usable window at room temperature, so they agree rather than conflict.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w057 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)
- Note: Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other.
- A (#wexlune-draft-policy, mavrix): When Wexlune Press deletes a FolioNest draft, it's permanently gone immediately. There's no recovery bin or grace period for any of their drafts.
- B (#wexlune-draft-recovery, yulcen): Every deleted FolioNest draft at Wexlune Press enters a mandatory 30-day recovery bin. It's recoverable for all 30 days; immediate permanent deletion isn't available.

#### w058 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #zenvora-informe filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects their own report-access instruction and retracts the unrestricted link.
- A (#zenvora-informe, ovrisa): El informe ToneHarbor de Zenvora Instruments se puede abrir con el enlace sin iniciar sesión. Lo dejé como acceso para cualquiera.
- B (#zenvora-informe-correcciones, ovrisa): Corrijo mi instrucción anterior: el informe ToneHarbor de Zenvora Instruments es solo para cuentas invitadas. Retiré el enlace abierto y mi aviso anterior queda sin efecto; hay que iniciar sesión.

## Run 2 — 2026-11-07T00:30:33+00:00

- Run (UTC): 2026-11-07T00:30:33+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 167.34s
- LLM calls: 98 (mean latency 1.351s per call)
- Token usage: input=166195, output=15321, total=181516 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.900 |
| F1 | 0.947 |
| TP / FP / FN / TN | 18 / 0 / 2 / 40 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 18 | 0 | 1 | 1 |
| update | 0 | 8 | 0 | 2 |
| compatible | 0 | 0 | 15 | 0 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (4)

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: Both claims state the same 12-hour (1,440-minute) usable window at room temperature, so they agree rather than conflict.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w057 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)
- Note: Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other.
- A (#wexlune-draft-policy, mavrix): When Wexlune Press deletes a FolioNest draft, it's permanently gone immediately. There's no recovery bin or grace period for any of their drafts.
- B (#wexlune-draft-recovery, yulcen): Every deleted FolioNest draft at Wexlune Press enters a mandatory 30-day recovery bin. It's recoverable for all 30 days; immediate permanent deletion isn't available.

#### w058 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #zenvora-informe filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects their own report-access instruction and retracts the unrestricted link.
- A (#zenvora-informe, ovrisa): El informe ToneHarbor de Zenvora Instruments se puede abrir con el enlace sin iniciar sesión. Lo dejé como acceso para cualquiera.
- B (#zenvora-informe-correcciones, ovrisa): Corrijo mi instrucción anterior: el informe ToneHarbor de Zenvora Instruments es solo para cuentas invitadas. Retiré el enlace abierto y mi aviso anterior queda sin efecto; hay que iniciar sesión.

## Run 3 — 2026-11-07T00:37:40+00:00

- Run (UTC): 2026-11-07T00:37:40+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 163.00s
- LLM calls: 98 (mean latency 1.283s per call)
- Token usage: input=166220, output=15225, total=181445 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.900 |
| F1 | 0.947 |
| TP / FP / FN / TN | 18 / 0 / 2 / 40 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 18 | 0 | 1 | 1 |
| update | 0 | 8 | 0 | 2 |
| compatible | 0 | 0 | 15 | 0 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (4)

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: Both claims state the same 12-hour (1,440-minute) usable window at room temperature, so they agree rather than conflict.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w057 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)
- Note: Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other.
- A (#wexlune-draft-policy, mavrix): When Wexlune Press deletes a FolioNest draft, it's permanently gone immediately. There's no recovery bin or grace period for any of their drafts.
- B (#wexlune-draft-recovery, yulcen): Every deleted FolioNest draft at Wexlune Press enters a mandatory 30-day recovery bin. It's recoverable for all 30 days; immediate permanent deletion isn't available.

#### w058 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #zenvora-informe filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects their own report-access instruction and retracts the unrestricted link.
- A (#zenvora-informe, ovrisa): El informe ToneHarbor de Zenvora Instruments se puede abrir con el enlace sin iniciar sesión. Lo dejé como acceso para cualquiera.
- B (#zenvora-informe-correcciones, ovrisa): Corrijo mi instrucción anterior: el informe ToneHarbor de Zenvora Instruments es solo para cuentas invitadas. Retiré el enlace abierto y mi aviso anterior queda sin efecto; hay que iniciar sesión.

<!-- splitbrain-live-runs [{"run_utc":"2026-11-07T00:23:08+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":173.422,"llm_calls":98,"mean_latency_s":1.3453,"usage_reported":true,"prompt_tokens":166206,"completion_tokens":15300,"total_tokens":181506,"tp":18,"fp":0,"fn":2,"tn":40,"precision":1.0,"recall":0.9,"f1":0.9473684210526316,"matrix":{"contradiction:contradiction":18,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":1,"update:contradiction":0,"update:update":8,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":15,"compatible:unrelated":0,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"Both claims state the same 12-hour (1,440-minute) usable window at room temperature, so they agree rather than conflict.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."}]},{"run_utc":"2026-11-07T00:30:33+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":167.344,"llm_calls":98,"mean_latency_s":1.3514,"usage_reported":true,"prompt_tokens":166195,"completion_tokens":15321,"total_tokens":181516,"tp":18,"fp":0,"fn":2,"tn":40,"precision":1.0,"recall":0.9,"f1":0.9473684210526316,"matrix":{"contradiction:contradiction":18,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":1,"update:contradiction":0,"update:update":8,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":15,"compatible:unrelated":0,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"Both claims state the same 12-hour (1,440-minute) usable window at room temperature, so they agree rather than conflict.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."}]},{"run_utc":"2026-11-07T00:37:40+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":163.0,"llm_calls":98,"mean_latency_s":1.2828,"usage_reported":true,"prompt_tokens":166220,"completion_tokens":15225,"total_tokens":181445,"tp":18,"fp":0,"fn":2,"tn":40,"precision":1.0,"recall":0.9,"f1":0.9473684210526316,"matrix":{"contradiction:contradiction":18,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":1,"update:contradiction":0,"update:update":8,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":15,"compatible:unrelated":0,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"Both claims state the same 12-hour (1,440-minute) usable window at room temperature, so they agree rather than conflict.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."}]}] -->
