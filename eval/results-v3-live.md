# Splitbrain — live brain evaluation

This report uses the generalized prefilter introduced in `7ddd17a`. Compare the [original prefilter (`f43f3e3`)](results-v3-live-before-prefilter.md) on the same frozen v3 dataset.

- Latest run (UTC): 2026-11-06T20:35:08+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v3.jsonl` — 60 pairs (contradiction=20, update=10, compatible=15, unrelated=15)
- Language mix: en=42, es=12, mixed=6
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=445937, output=46428, total=492365 (mean per run: 148646 in / 15476 out / 164122 total; API dollar costs are not estimated).

## Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T20:29:06+00:00 | 1.000 | 0.900 | 0.947 | 18 / 0 / 2 / 40 | 9 | 89 | 192.47s | 1.806s | 148656 / 15519 / 164175 |
| 2 | 2026-11-06T20:32:19+00:00 | 1.000 | 0.900 | 0.947 | 18 / 0 / 2 / 40 | 9 | 89 | 168.02s | 1.530s | 148643 / 15405 / 164048 |
| 3 | 2026-11-06T20:35:08+00:00 | 1.000 | 0.900 | 0.947 | 18 / 0 / 2 / 40 | 9 | 89 | 170.39s | 1.560s | 148638 / 15504 / 164142 |
| **Mean** | — | **1.000** | **0.900** | **0.947** | 18.0 / 0.0 / 2.0 / 40.0 | 9.0 | 89.0 | 176.96s | 1.632s | 148646 / 15476 / 164122 |

## Run 1 — 2026-11-06T20:29:06+00:00

- Run (UTC): 2026-11-06T20:29:06+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 192.47s
- LLM calls: 89 (mean latency 1.806s per call)
- Token usage: input=148656, output=15519, total=164175 (costs are not estimated)

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
| compatible | 0 | 0 | 10 | 5 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (9)

#### w002 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: An invited preview and general availability are separate milestones of the same release.
- A (#brintle-preview, sivran): DomeRelay preview for Brintle Observatory opens March 8, invited schedulers only. Invites are ready.
- B (#brintle-rollout, druvika): May 2 is DomeRelay general availability at Brintle Observatory, after the March preview. That's when anyone there can sign up.

#### w007 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: A first-response deadline and a resolution deadline measure different stages of the same incident.
- A (#qorlen-service-desk, elhavi): Qorlen Tidal's MoorLatch critical incidents get a human first response within 30 minutes, any day. Auto receipts don't count.
- B (#qorlen-restoration, roxali): For those MoorLatch critical incidents at Qorlen Tidal, the resolution SLA is eight hours from the original ticket. Separate clock from the first response.

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: 1,440 minutes equals 12 hours, so both statements describe the same usable window.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w031 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening.
- A (#ivrel-service-hours, farxel): CastPilot support for Ivrel Foundry responds within one hour during staffed coverage, weekdays 09:00-17:00. Outside those hours the response clock waits for the next opening.
- B (#ivrel-evening-handover, zyveta): Ivrel Foundry tickets arriving at 18:00 go into the CastPilot queue for 09:00 the next working day. Nobody is assigned to respond overnight.

#### w043 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: Hardware pickup and account activation are different steps of the same deployment.
- A (#zenvora-kit-pickup, avrel): ToneHarbor kits for Zenvora Instruments: pickup Monday. Packed + ready for the rehearsal rooms.
- B (#zenvora-account-activation, noxeli): ToneHarbor accounts for Zenvora Instruments activate Thursday, after Monday's kit pickup. Having the hardware earlier doesn't activate the accounts.

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

#### w059 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: The key-collection window fits within the stated reservation hold.
- A (#jorvane-reservation-holds, zavren): Jorvane Bikes will hold the SpokeHarbor group reservation until Friday at 18:00 local time. The bikes won't be released to anyone else before then.
- B (#jorvane-key-desk, elhavi): For that Jorvane Bikes SpokeHarbor group reservation, collect the keys Friday between 16:00 and 18:00 local time. We have staff at the key desk for that window.

## Run 2 — 2026-11-06T20:32:19+00:00

- Run (UTC): 2026-11-06T20:32:19+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 168.02s
- LLM calls: 89 (mean latency 1.530s per call)
- Token usage: input=148643, output=15405, total=164048 (costs are not estimated)

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
| compatible | 0 | 0 | 10 | 5 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (9)

#### w002 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: An invited preview and general availability are separate milestones of the same release.
- A (#brintle-preview, sivran): DomeRelay preview for Brintle Observatory opens March 8, invited schedulers only. Invites are ready.
- B (#brintle-rollout, druvika): May 2 is DomeRelay general availability at Brintle Observatory, after the March preview. That's when anyone there can sign up.

#### w007 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: A first-response deadline and a resolution deadline measure different stages of the same incident.
- A (#qorlen-service-desk, elhavi): Qorlen Tidal's MoorLatch critical incidents get a human first response within 30 minutes, any day. Auto receipts don't count.
- B (#qorlen-restoration, roxali): For those MoorLatch critical incidents at Qorlen Tidal, the resolution SLA is eight hours from the original ticket. Separate clock from the first response.

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: 1,440 minutes equals 12 hours, so both statements describe the same usable window.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w031 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening.
- A (#ivrel-service-hours, farxel): CastPilot support for Ivrel Foundry responds within one hour during staffed coverage, weekdays 09:00-17:00. Outside those hours the response clock waits for the next opening.
- B (#ivrel-evening-handover, zyveta): Ivrel Foundry tickets arriving at 18:00 go into the CastPilot queue for 09:00 the next working day. Nobody is assigned to respond overnight.

#### w043 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: Hardware pickup and account activation are different steps of the same deployment.
- A (#zenvora-kit-pickup, avrel): ToneHarbor kits for Zenvora Instruments: pickup Monday. Packed + ready for the rehearsal rooms.
- B (#zenvora-account-activation, noxeli): ToneHarbor accounts for Zenvora Instruments activate Thursday, after Monday's kit pickup. Having the hardware earlier doesn't activate the accounts.

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

#### w059 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: The key-collection window fits within the stated reservation hold.
- A (#jorvane-reservation-holds, zavren): Jorvane Bikes will hold the SpokeHarbor group reservation until Friday at 18:00 local time. The bikes won't be released to anyone else before then.
- B (#jorvane-key-desk, elhavi): For that Jorvane Bikes SpokeHarbor group reservation, collect the keys Friday between 16:00 and 18:00 local time. We have staff at the key desk for that window.

## Run 3 — 2026-11-06T20:35:08+00:00

- Run (UTC): 2026-11-06T20:35:08+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 170.39s
- LLM calls: 89 (mean latency 1.560s per call)
- Token usage: input=148638, output=15504, total=164142 (costs are not estimated)

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
| compatible | 0 | 0 | 10 | 5 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (9)

#### w002 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: An invited preview and general availability are separate milestones of the same release.
- A (#brintle-preview, sivran): DomeRelay preview for Brintle Observatory opens March 8, invited schedulers only. Invites are ready.
- B (#brintle-rollout, druvika): May 2 is DomeRelay general availability at Brintle Observatory, after the March preview. That's when anyone there can sign up.

#### w007 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: A first-response deadline and a resolution deadline measure different stages of the same incident.
- A (#qorlen-service-desk, elhavi): Qorlen Tidal's MoorLatch critical incidents get a human first response within 30 minutes, any day. Auto receipts don't count.
- B (#qorlen-restoration, roxali): For those MoorLatch critical incidents at Qorlen Tidal, the resolution SLA is eight hours from the original ticket. Separate clock from the first response.

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: 1,440 minutes equals 12 hours, so both statements describe the same usable window.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w031 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening.
- A (#ivrel-service-hours, farxel): CastPilot support for Ivrel Foundry responds within one hour during staffed coverage, weekdays 09:00-17:00. Outside those hours the response clock waits for the next opening.
- B (#ivrel-evening-handover, zyveta): Ivrel Foundry tickets arriving at 18:00 go into the CastPilot queue for 09:00 the next working day. Nobody is assigned to respond overnight.

#### w043 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: Hardware pickup and account activation are different steps of the same deployment.
- A (#zenvora-kit-pickup, avrel): ToneHarbor kits for Zenvora Instruments: pickup Monday. Packed + ready for the rehearsal rooms.
- B (#zenvora-account-activation, noxeli): ToneHarbor accounts for Zenvora Instruments activate Thursday, after Monday's kit pickup. Having the hardware earlier doesn't activate the accounts.

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

#### w059 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: The key-collection window fits within the stated reservation hold.
- A (#jorvane-reservation-holds, zavren): Jorvane Bikes will hold the SpokeHarbor group reservation until Friday at 18:00 local time. The bikes won't be released to anyone else before then.
- B (#jorvane-key-desk, elhavi): For that Jorvane Bikes SpokeHarbor group reservation, collect the keys Friday between 16:00 and 18:00 local time. We have staff at the key desk for that window.

<!-- splitbrain-live-runs [{"run_utc":"2026-11-06T20:29:06+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":192.468,"llm_calls":89,"mean_latency_s":1.8061,"usage_reported":true,"prompt_tokens":148656,"completion_tokens":15519,"total_tokens":164175,"tp":18,"fp":0,"fn":2,"tn":40,"precision":1.0,"recall":0.9,"f1":0.9473684210526316,"matrix":{"contradiction:contradiction":18,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":1,"update:contradiction":0,"update:update":8,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":10,"compatible:unrelated":5,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w002","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"An invited preview and general availability are separate milestones of the same release."},{"id":"w007","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"A first-response deadline and a resolution deadline measure different stages of the same incident."},{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"1,440 minutes equals 12 hours, so both statements describe the same usable window.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w031","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening."},{"id":"w043","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"Hardware pickup and account activation are different steps of the same deployment."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."},{"id":"w059","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"The key-collection window fits within the stated reservation hold."}]},{"run_utc":"2026-11-06T20:32:19+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":168.016,"llm_calls":89,"mean_latency_s":1.5305,"usage_reported":true,"prompt_tokens":148643,"completion_tokens":15405,"total_tokens":164048,"tp":18,"fp":0,"fn":2,"tn":40,"precision":1.0,"recall":0.9,"f1":0.9473684210526316,"matrix":{"contradiction:contradiction":18,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":1,"update:contradiction":0,"update:update":8,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":10,"compatible:unrelated":5,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w002","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"An invited preview and general availability are separate milestones of the same release."},{"id":"w007","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"A first-response deadline and a resolution deadline measure different stages of the same incident."},{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"1,440 minutes equals 12 hours, so both statements describe the same usable window.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w031","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening."},{"id":"w043","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"Hardware pickup and account activation are different steps of the same deployment."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."},{"id":"w059","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"The key-collection window fits within the stated reservation hold."}]},{"run_utc":"2026-11-06T20:35:08+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":170.391,"llm_calls":89,"mean_latency_s":1.5603,"usage_reported":true,"prompt_tokens":148638,"completion_tokens":15504,"total_tokens":164142,"tp":18,"fp":0,"fn":2,"tn":40,"precision":1.0,"recall":0.9,"f1":0.9473684210526316,"matrix":{"contradiction:contradiction":18,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":1,"update:contradiction":0,"update:update":8,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":10,"compatible:unrelated":5,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w002","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"An invited preview and general availability are separate milestones of the same release."},{"id":"w007","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"A first-response deadline and a resolution deadline measure different stages of the same incident."},{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"1,440 minutes equals 12 hours, so both statements describe the same usable window.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w031","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening."},{"id":"w043","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"Hardware pickup and account activation are different steps of the same deployment."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."},{"id":"w059","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"The key-collection window fits within the stated reservation hold."}]}] -->
