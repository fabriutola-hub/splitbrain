# Splitbrain — live brain evaluation

This report uses the original prefilter from commit `f43f3e3`, before generalization. Compare the [generalized prefilter results](results-v3-live.md) on the same frozen v3 dataset.

- Latest run (UTC): 2026-11-06T20:33:52+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v3.jsonl` — 60 pairs (contradiction=20, update=10, compatible=15, unrelated=15)
- Language mix: en=42, es=12, mixed=6
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=290271, output=30038, total=320309 (mean per run: 96757 in / 10013 out / 106770 total; API dollar costs are not estimated).

## Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T20:29:13+00:00 | 1.000 | 0.650 | 0.788 | 13 / 0 / 7 / 40 | 20 | 57 | 113.41s | 1.628s | 96754 / 10005 / 106759 |
| 2 | 2026-11-06T20:31:07+00:00 | 1.000 | 0.600 | 0.750 | 12 / 0 / 8 / 40 | 21 | 57 | 163.25s | 2.511s | 96747 / 10035 / 106782 |
| 3 | 2026-11-06T20:33:52+00:00 | 1.000 | 0.650 | 0.788 | 13 / 0 / 7 / 40 | 20 | 57 | 111.88s | 1.609s | 96770 / 9998 / 106768 |
| **Mean** | — | **1.000** | **0.633** | **0.775** | 12.7 / 0.0 / 7.3 / 40.0 | 20.3 | 57.0 | 129.51s | 1.916s | 96757 / 10013 / 106770 |

## Run 1 — 2026-11-06T20:29:13+00:00

- Run (UTC): 2026-11-06T20:29:13+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 113.41s
- LLM calls: 57 (mean latency 1.628s per call)
- Token usage: input=96754, output=10005, total=106759 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.650 |
| F1 | 0.788 |
| TP / FP / FN / TN | 13 / 0 / 7 / 40 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 13 | 0 | 1 | 6 |
| update | 0 | 6 | 0 | 4 |
| compatible | 0 | 0 | 6 | 9 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (20)

#### w002 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: An invited preview and general availability are separate milestones of the same release.
- A (#brintle-preview, sivran): DomeRelay preview for Brintle Observatory opens March 8, invited schedulers only. Invites are ready.
- B (#brintle-rollout, druvika): May 2 is DomeRelay general availability at Brintle Observatory, after the March preview. That's when anyone there can sign up.

#### w004 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #wexlune-proofing filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects their own proof-copy count and withdraws the earlier number.
- A (#wexlune-proofing, querel): FolioNest proofs for Wexlune Press: 75 copies. Sending to print, fyi.
- B (#wexlune-printdesk, querel): Correction to my 75-copy message: I counted the rejected proofs too. Wexlune needs 57 FolioNest proofs, not 75. Please discard my earlier number.

#### w007 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #qorlen-restoration filtered out: no commitment signal (pure chatter)
- Note: A first-response deadline and a resolution deadline measure different stages of the same incident.
- A (#qorlen-service-desk, elhavi): Qorlen Tidal's MoorLatch critical incidents get a human first response within 30 minutes, any day. Auto receipts don't count.
- B (#qorlen-restoration, roxali): For those MoorLatch critical incidents at Qorlen Tidal, the resolution SLA is eight hours from the original ticket. Separate clock from the first response.

#### w008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ivrel-calibracion filtered out: no commitment signal (pure chatter)
- Note: The same permitted dimensional tolerance is stated in millimetres and centimetres with an unchanged numeric value.
- A (#ivrel-calibracion, vinzel): CastPilot en Ivrel Foundry acepta una desviación máxima de ±0,4 mm en las piezas del lote de hoy. Ese es el valor final de producción.
- B (#ivrel-lote, delvyn): El límite final para el lote de hoy de Ivrel Foundry en CastPilot es ±0,4 cm. Una pieza dentro de ese margen pasa, ya lo dejé indicado.

#### w012 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ulnexa-acuerdos filtered out: no commitment signal (pure chatter)
- Note: The same uptime commitment both includes and excludes planned maintenance from its measurement.
- A (#ulnexa-acuerdos, noxeli): Firmado con Ulnexa Optics: PrismDock tiene 99,8 % de disponibilidad mensual contando todas las paradas, incluso mantenimiento planificado. No hay exclusiones.
- B (#ulnexa-service-metrics, sivran): For Ulnexa Optics' signed PrismDock 99.8% monthly SLA, planned maintenance is excluded from the denominator. That's the agreed calculation, not an internal dashboard shortcut.

#### w013 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #peldris-metering filtered out: no commitment signal (pure chatter)
- Note: The two prices are equal after converting the quoted water-volume basis.
- A (#peldris-quotes, druvika): FinMosaic treatment @ Peldris Aquatics: EUR 2.40 / 100 litres. No fixed fee on top.
- B (#peldris-metering, talven): Peldris Aquatics' FinMosaic rate works out to EUR 24 per 1,000 litres, with no additional fixed fee. That's the figure in the meter sheet.

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w016 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #elnovar-deliverables filtered out: no commitment signal (pure chatter)
- Note: All files in the same export batch are required to use two different encodings.
- A (#elnovar-deliverables, yulcen): Elnovar Maps signed off the ContourLamp index export for batch R7 as UTF-8. Every index file in that batch must use UTF-8, no alternate copy.
- B (#elnovar-export-desk, ovrisa): Batch R7's final ContourLamp index delivery to Elnovar Maps is UTF-16 only, for every index file. UTF-8 files aren't accepted in this delivery.

#### w017 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #dovrane-degustaciones filtered out: no commitment signal (pure chatter)
- Note: The base daily limit explicitly allows signed waivers, and the higher count has such a waiver.
- A (#dovrane-degustaciones, zavren): En SteepLedger el máximo normal de Dovrane Tea es 4 degustaciones por día, salvo que haya una dispensa firmada por la dirección.
- B (#dovrane-permisos, elhavi): La dirección firmó la dispensa para el 12 de abril de Dovrane Tea: ese día SteepLedger admite 6 degustaciones. Está adjunta al turno, todo aprobado.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: 1,440 minutes equals 12 hours, so both statements describe the same usable window.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w026 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #otharyn-show-control filtered out: no commitment signal (pure chatter)
- Note: Publishing the same show requires two independent approvers in one policy and only one in the other.
- A (#otharyn-show-control, yulcen): Every Otharyn Theatre show needs two independent approvals in CueSpindle before it can go live. One person's approval never suffices.
- B (#otharyn-publish-desk, ovrisa): CueSpindle publishing at Otharyn Theatre needs only the stage manager's approval, for every show. A second sign-off is not required to go live.

#### w028 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #kivrane-fixture-counts filtered out: no commitment signal (pure chatter)
- Note: A per-run fixture limit and a simultaneous-run limit can both apply.
- A (#kivrane-fixture-counts, roxali): Each BeamLedger run at Kivrane Lighting can address at most 60 fixtures. Bigger sets need multiple runs.
- B (#kivrane-run-scheduling, vinzel): Kivrane Lighting can have four BeamLedger runs active at once. The 60-fixture limit still applies separately to each run.

#### w031 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #ivrel-evening-handover filtered out: no commitment signal (pure chatter)
- Note: A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening.
- A (#ivrel-service-hours, farxel): CastPilot support for Ivrel Foundry responds within one hour during staffed coverage, weekdays 09:00-17:00. Outside those hours the response clock waits for the next opening.
- B (#ivrel-evening-handover, zyveta): Ivrel Foundry tickets arriving at 18:00 go into the CastPilot queue for 09:00 the next working day. Nobody is assigned to respond overnight.

#### w033 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #qorlen-muestreo filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects the interval in their earlier sensor configuration message.
- A (#qorlen-muestreo, sivran): Dejé MoorLatch tomando una lectura de Qorlen Tidal cada 90 minutos. Lo anoto acá para el relevo.
- B (#qorlen-relevo, sivran): Corrección a lo que escribí del muestreo: son 90 segundos, no 90 minutos. La configuración de MoorLatch de Qorlen Tidal es cada 90 segundos; mi nota anterior tenía mal la unidad.

#### w039 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #otharyn-audio filtered out: no commitment signal (pure chatter)
- Note: Forty-eight kilohertz and forty-eight thousand samples per second express the same sampling rate.
- A (#otharyn-audio, vinzel): El audio de CueSpindle para Otharyn Theatre va a 48 kHz. Es la frecuencia acordada para la grabación completa.
- B (#otharyn-grabacion, delvyn): Anotado para Otharyn Theatre: la grabación completa de CueSpindle usa 48.000 muestras por segundo. No hace falta convertir la frecuencia al entregar.

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

#### w060 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #tazvori-advance-order filtered out: no commitment signal (pure chatter)
- Note: The same signed advance invoice has an identical numeric amount but two different required currencies.
- A (#tazvori-advance-order, roxali): StoneQuiver advance invoice D19 for Tazvori Quarry is signed at EUR 400, payable in euros. The invoice has no currency-conversion option.
- B (#tazvori-payment-desk, vinzel): Tazvori Quarry's signed StoneQuiver advance invoice D19 is GBP 400, payable only in pounds. Please arrange the GBP payment against D19.

## Run 2 — 2026-11-06T20:31:07+00:00

- Run (UTC): 2026-11-06T20:31:07+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 163.25s
- LLM calls: 57 (mean latency 2.511s per call)
- Token usage: input=96747, output=10035, total=106782 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.600 |
| F1 | 0.750 |
| TP / FP / FN / TN | 12 / 0 / 8 / 40 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 12 | 0 | 1 | 7 |
| update | 0 | 6 | 0 | 4 |
| compatible | 0 | 0 | 6 | 9 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (21)

#### w002 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: An invited preview and general availability are separate milestones of the same release.
- A (#brintle-preview, sivran): DomeRelay preview for Brintle Observatory opens March 8, invited schedulers only. Invites are ready.
- B (#brintle-rollout, druvika): May 2 is DomeRelay general availability at Brintle Observatory, after the March preview. That's when anyone there can sign up.

#### w004 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #wexlune-proofing filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects their own proof-copy count and withdraws the earlier number.
- A (#wexlune-proofing, querel): FolioNest proofs for Wexlune Press: 75 copies. Sending to print, fyi.
- B (#wexlune-printdesk, querel): Correction to my 75-copy message: I counted the rejected proofs too. Wexlune needs 57 FolioNest proofs, not 75. Please discard my earlier number.

#### w007 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #qorlen-restoration filtered out: no commitment signal (pure chatter)
- Note: A first-response deadline and a resolution deadline measure different stages of the same incident.
- A (#qorlen-service-desk, elhavi): Qorlen Tidal's MoorLatch critical incidents get a human first response within 30 minutes, any day. Auto receipts don't count.
- B (#qorlen-restoration, roxali): For those MoorLatch critical incidents at Qorlen Tidal, the resolution SLA is eight hours from the original ticket. Separate clock from the first response.

#### w008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ivrel-calibracion filtered out: no commitment signal (pure chatter)
- Note: The same permitted dimensional tolerance is stated in millimetres and centimetres with an unchanged numeric value.
- A (#ivrel-calibracion, vinzel): CastPilot en Ivrel Foundry acepta una desviación máxima de ±0,4 mm en las piezas del lote de hoy. Ese es el valor final de producción.
- B (#ivrel-lote, delvyn): El límite final para el lote de hoy de Ivrel Foundry en CastPilot es ±0,4 cm. Una pieza dentro de ese margen pasa, ya lo dejé indicado.

#### w012 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ulnexa-acuerdos filtered out: no commitment signal (pure chatter)
- Note: The same uptime commitment both includes and excludes planned maintenance from its measurement.
- A (#ulnexa-acuerdos, noxeli): Firmado con Ulnexa Optics: PrismDock tiene 99,8 % de disponibilidad mensual contando todas las paradas, incluso mantenimiento planificado. No hay exclusiones.
- B (#ulnexa-service-metrics, sivran): For Ulnexa Optics' signed PrismDock 99.8% monthly SLA, planned maintenance is excluded from the denominator. That's the agreed calculation, not an internal dashboard shortcut.

#### w013 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #peldris-metering filtered out: no commitment signal (pure chatter)
- Note: The two prices are equal after converting the quoted water-volume basis.
- A (#peldris-quotes, druvika): FinMosaic treatment @ Peldris Aquatics: EUR 2.40 / 100 litres. No fixed fee on top.
- B (#peldris-metering, talven): Peldris Aquatics' FinMosaic rate works out to EUR 24 per 1,000 litres, with no additional fixed fee. That's the figure in the meter sheet.

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w016 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #elnovar-deliverables filtered out: no commitment signal (pure chatter)
- Note: All files in the same export batch are required to use two different encodings.
- A (#elnovar-deliverables, yulcen): Elnovar Maps signed off the ContourLamp index export for batch R7 as UTF-8. Every index file in that batch must use UTF-8, no alternate copy.
- B (#elnovar-export-desk, ovrisa): Batch R7's final ContourLamp index delivery to Elnovar Maps is UTF-16 only, for every index file. UTF-8 files aren't accepted in this delivery.

#### w017 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #dovrane-degustaciones filtered out: no commitment signal (pure chatter)
- Note: The base daily limit explicitly allows signed waivers, and the higher count has such a waiver.
- A (#dovrane-degustaciones, zavren): En SteepLedger el máximo normal de Dovrane Tea es 4 degustaciones por día, salvo que haya una dispensa firmada por la dirección.
- B (#dovrane-permisos, elhavi): La dirección firmó la dispensa para el 12 de abril de Dovrane Tea: ese día SteepLedger admite 6 degustaciones. Está adjunta al turno, todo aprobado.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: 1,440 minutes equals 12 hours, so both statements describe the same usable window.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w026 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #otharyn-show-control filtered out: no commitment signal (pure chatter)
- Note: Publishing the same show requires two independent approvers in one policy and only one in the other.
- A (#otharyn-show-control, yulcen): Every Otharyn Theatre show needs two independent approvals in CueSpindle before it can go live. One person's approval never suffices.
- B (#otharyn-publish-desk, ovrisa): CueSpindle publishing at Otharyn Theatre needs only the stage manager's approval, for every show. A second sign-off is not required to go live.

#### w028 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #kivrane-fixture-counts filtered out: no commitment signal (pure chatter)
- Note: A per-run fixture limit and a simultaneous-run limit can both apply.
- A (#kivrane-fixture-counts, roxali): Each BeamLedger run at Kivrane Lighting can address at most 60 fixtures. Bigger sets need multiple runs.
- B (#kivrane-run-scheduling, vinzel): Kivrane Lighting can have four BeamLedger runs active at once. The 60-fixture limit still applies separately to each run.

#### w031 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #ivrel-evening-handover filtered out: no commitment signal (pure chatter)
- Note: A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening.
- A (#ivrel-service-hours, farxel): CastPilot support for Ivrel Foundry responds within one hour during staffed coverage, weekdays 09:00-17:00. Outside those hours the response clock waits for the next opening.
- B (#ivrel-evening-handover, zyveta): Ivrel Foundry tickets arriving at 18:00 go into the CastPilot queue for 09:00 the next working day. Nobody is assigned to respond overnight.

#### w033 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #qorlen-muestreo filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects the interval in their earlier sensor configuration message.
- A (#qorlen-muestreo, sivran): Dejé MoorLatch tomando una lectura de Qorlen Tidal cada 90 minutos. Lo anoto acá para el relevo.
- B (#qorlen-relevo, sivran): Corrección a lo que escribí del muestreo: son 90 segundos, no 90 minutos. La configuración de MoorLatch de Qorlen Tidal es cada 90 segundos; mi nota anterior tenía mal la unidad.

#### w039 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #otharyn-audio filtered out: no commitment signal (pure chatter)
- Note: Forty-eight kilohertz and forty-eight thousand samples per second express the same sampling rate.
- A (#otharyn-audio, vinzel): El audio de CueSpindle para Otharyn Theatre va a 48 kHz. Es la frecuencia acordada para la grabación completa.
- B (#otharyn-grabacion, delvyn): Anotado para Otharyn Theatre: la grabación completa de CueSpindle usa 48.000 muestras por segundo. No hace falta convertir la frecuencia al entregar.

#### w043 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: Hardware pickup and account activation are different steps of the same deployment.
- A (#zenvora-kit-pickup, avrel): ToneHarbor kits for Zenvora Instruments: pickup Monday. Packed + ready for the rehearsal rooms.
- B (#zenvora-account-activation, noxeli): ToneHarbor accounts for Zenvora Instruments activate Thursday, after Monday's kit pickup. Having the hardware earlier doesn't activate the accounts.

#### w050 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The claims concern different subjects — the workshop's end time (17:30) versus its start time (16:00) — so they do not directly conflict.
- Note: The same workshop starts at the same time but is booked for incompatible end times and durations.
- A (#trevori-session-plan, vinzel): Trevori Ceramics' March 20 GlazeRail workshop starts at 16:00 and lasts 90 minutes, finishing at 17:30. That's the published session, all in local time.
- B (#trevori-tutor-booking, delvyn): The published March 20 GlazeRail workshop at Trevori Ceramics runs 16:00-16:45 local time, exactly 45 minutes. The full workshop ends at 16:45, not just a break.

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

#### w060 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #tazvori-advance-order filtered out: no commitment signal (pure chatter)
- Note: The same signed advance invoice has an identical numeric amount but two different required currencies.
- A (#tazvori-advance-order, roxali): StoneQuiver advance invoice D19 for Tazvori Quarry is signed at EUR 400, payable in euros. The invoice has no currency-conversion option.
- B (#tazvori-payment-desk, vinzel): Tazvori Quarry's signed StoneQuiver advance invoice D19 is GBP 400, payable only in pounds. Please arrange the GBP payment against D19.

## Run 3 — 2026-11-06T20:33:52+00:00

- Run (UTC): 2026-11-06T20:33:52+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 111.88s
- LLM calls: 57 (mean latency 1.609s per call)
- Token usage: input=96770, output=9998, total=106768 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 1.000 |
| recall | 0.650 |
| F1 | 0.788 |
| TP / FP / FN / TN | 13 / 0 / 7 / 40 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 13 | 0 | 1 | 6 |
| update | 0 | 6 | 0 | 4 |
| compatible | 0 | 0 | 6 | 9 |
| unrelated | 0 | 0 | 0 | 15 |

### Errors (20)

#### w002 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: An invited preview and general availability are separate milestones of the same release.
- A (#brintle-preview, sivran): DomeRelay preview for Brintle Observatory opens March 8, invited schedulers only. Invites are ready.
- B (#brintle-rollout, druvika): May 2 is DomeRelay general availability at Brintle Observatory, after the March preview. That's when anyone there can sign up.

#### w004 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #wexlune-proofing filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects their own proof-copy count and withdraws the earlier number.
- A (#wexlune-proofing, querel): FolioNest proofs for Wexlune Press: 75 copies. Sending to print, fyi.
- B (#wexlune-printdesk, querel): Correction to my 75-copy message: I counted the rejected proofs too. Wexlune needs 57 FolioNest proofs, not 75. Please discard my earlier number.

#### w007 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #qorlen-restoration filtered out: no commitment signal (pure chatter)
- Note: A first-response deadline and a resolution deadline measure different stages of the same incident.
- A (#qorlen-service-desk, elhavi): Qorlen Tidal's MoorLatch critical incidents get a human first response within 30 minutes, any day. Auto receipts don't count.
- B (#qorlen-restoration, roxali): For those MoorLatch critical incidents at Qorlen Tidal, the resolution SLA is eight hours from the original ticket. Separate clock from the first response.

#### w008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ivrel-calibracion filtered out: no commitment signal (pure chatter)
- Note: The same permitted dimensional tolerance is stated in millimetres and centimetres with an unchanged numeric value.
- A (#ivrel-calibracion, vinzel): CastPilot en Ivrel Foundry acepta una desviación máxima de ±0,4 mm en las piezas del lote de hoy. Ese es el valor final de producción.
- B (#ivrel-lote, delvyn): El límite final para el lote de hoy de Ivrel Foundry en CastPilot es ±0,4 cm. Una pieza dentro de ese margen pasa, ya lo dejé indicado.

#### w012 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ulnexa-acuerdos filtered out: no commitment signal (pure chatter)
- Note: The same uptime commitment both includes and excludes planned maintenance from its measurement.
- A (#ulnexa-acuerdos, noxeli): Firmado con Ulnexa Optics: PrismDock tiene 99,8 % de disponibilidad mensual contando todas las paradas, incluso mantenimiento planificado. No hay exclusiones.
- B (#ulnexa-service-metrics, sivran): For Ulnexa Optics' signed PrismDock 99.8% monthly SLA, planned maintenance is excluded from the denominator. That's the agreed calculation, not an internal dashboard shortcut.

#### w013 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #peldris-metering filtered out: no commitment signal (pure chatter)
- Note: The two prices are equal after converting the quoted water-volume basis.
- A (#peldris-quotes, druvika): FinMosaic treatment @ Peldris Aquatics: EUR 2.40 / 100 litres. No fixed fee on top.
- B (#peldris-metering, talven): Peldris Aquatics' FinMosaic rate works out to EUR 24 per 1,000 litres, with no additional fixed fee. That's the figure in the meter sheet.

#### w014 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #ravulon-riego filtered out: no commitment signal (pure chatter)
- Note: The author corrects their own reminder time from evening to morning.
- A (#ravulon-riego, isvani): Programé el recordatorio RootStencil para Ravulon Gardens a las 10 de la noche todos los días. Aviso por si lo ven en el calendario.
- B (#ravulon-calendario, isvani): Me corrijo: lo de RootStencil de mi mensaje anterior es a las 10 de la mañana, no de la noche. Ya corregí mi evento; ignoren la hora que puse antes.

#### w016 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #elnovar-deliverables filtered out: no commitment signal (pure chatter)
- Note: All files in the same export batch are required to use two different encodings.
- A (#elnovar-deliverables, yulcen): Elnovar Maps signed off the ContourLamp index export for batch R7 as UTF-8. Every index file in that batch must use UTF-8, no alternate copy.
- B (#elnovar-export-desk, ovrisa): Batch R7's final ContourLamp index delivery to Elnovar Maps is UTF-16 only, for every index file. UTF-8 files aren't accepted in this delivery.

#### w017 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #dovrane-degustaciones filtered out: no commitment signal (pure chatter)
- Note: The base daily limit explicitly allows signed waivers, and the higher count has such a waiver.
- A (#dovrane-degustaciones, zavren): En SteepLedger el máximo normal de Dovrane Tea es 4 degustaciones por día, salvo que haya una dispensa firmada por la dirección.
- B (#dovrane-permisos, elhavi): La dirección firmó la dispensa para el 12 de abril de Dovrane Tea: ese día SteepLedger admite 6 degustaciones. Está adjunta al turno, todo aprobado.

#### w023 — label `contradiction`, predicted `compatible`

- Stage: `classification`, confidence=0.90
- Reason: 1,440 minutes equals 12 hours, so both statements describe the same usable window.
- Note: The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other.
- A (#vorlith-materials, sivran): Once opened, the ResinHatch resin for Vorlith Moulds is usable for exactly 12 hours, then it must be discarded. Room-temperature storage throughout.
- B (#vorlith-production-notes, druvika): Vorlith Moulds' ResinHatch resin stays usable for 1,440 minutes after opening at room temperature. It does not expire at 12 hours; discard it at the 1,440-minute mark.

#### w026 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #otharyn-show-control filtered out: no commitment signal (pure chatter)
- Note: Publishing the same show requires two independent approvers in one policy and only one in the other.
- A (#otharyn-show-control, yulcen): Every Otharyn Theatre show needs two independent approvals in CueSpindle before it can go live. One person's approval never suffices.
- B (#otharyn-publish-desk, ovrisa): CueSpindle publishing at Otharyn Theatre needs only the stage manager's approval, for every show. A second sign-off is not required to go live.

#### w028 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #kivrane-fixture-counts filtered out: no commitment signal (pure chatter)
- Note: A per-run fixture limit and a simultaneous-run limit can both apply.
- A (#kivrane-fixture-counts, roxali): Each BeamLedger run at Kivrane Lighting can address at most 60 fixtures. Bigger sets need multiple runs.
- B (#kivrane-run-scheduling, vinzel): Kivrane Lighting can have four BeamLedger runs active at once. The 60-fixture limit still applies separately to each run.

#### w031 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #ivrel-evening-handover filtered out: no commitment signal (pure chatter)
- Note: A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening.
- A (#ivrel-service-hours, farxel): CastPilot support for Ivrel Foundry responds within one hour during staffed coverage, weekdays 09:00-17:00. Outside those hours the response clock waits for the next opening.
- B (#ivrel-evening-handover, zyveta): Ivrel Foundry tickets arriving at 18:00 go into the CastPilot queue for 09:00 the next working day. Nobody is assigned to respond overnight.

#### w033 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #qorlen-muestreo filtered out: no commitment signal (pure chatter)
- Note: The author explicitly corrects the interval in their earlier sensor configuration message.
- A (#qorlen-muestreo, sivran): Dejé MoorLatch tomando una lectura de Qorlen Tidal cada 90 minutos. Lo anoto acá para el relevo.
- B (#qorlen-relevo, sivran): Corrección a lo que escribí del muestreo: son 90 segundos, no 90 minutos. La configuración de MoorLatch de Qorlen Tidal es cada 90 segundos; mi nota anterior tenía mal la unidad.

#### w039 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #otharyn-audio filtered out: no commitment signal (pure chatter)
- Note: Forty-eight kilohertz and forty-eight thousand samples per second express the same sampling rate.
- A (#otharyn-audio, vinzel): El audio de CueSpindle para Otharyn Theatre va a 48 kHz. Es la frecuencia acordada para la grabación completa.
- B (#otharyn-grabacion, delvyn): Anotado para Otharyn Theatre: la grabación completa de CueSpindle usa 48.000 muestras por segundo. No hace falta convertir la frecuencia al entregar.

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

#### w060 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #tazvori-advance-order filtered out: no commitment signal (pure chatter)
- Note: The same signed advance invoice has an identical numeric amount but two different required currencies.
- A (#tazvori-advance-order, roxali): StoneQuiver advance invoice D19 for Tazvori Quarry is signed at EUR 400, payable in euros. The invoice has no currency-conversion option.
- B (#tazvori-payment-desk, vinzel): Tazvori Quarry's signed StoneQuiver advance invoice D19 is GBP 400, payable only in pounds. Please arrange the GBP payment against D19.

<!-- splitbrain-live-runs [{"run_utc":"2026-11-06T20:29:13+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":113.406,"llm_calls":57,"mean_latency_s":1.6283,"usage_reported":true,"prompt_tokens":96754,"completion_tokens":10005,"total_tokens":106759,"tp":13,"fp":0,"fn":7,"tn":40,"precision":1.0,"recall":0.65,"f1":0.787878787878788,"matrix":{"contradiction:contradiction":13,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":6,"update:contradiction":0,"update:update":6,"update:compatible":0,"update:unrelated":4,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":6,"compatible:unrelated":9,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w002","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"An invited preview and general availability are separate milestones of the same release."},{"id":"w004","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-proofing filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own proof-copy count and withdraws the earlier number."},{"id":"w007","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #qorlen-restoration filtered out: no commitment signal (pure chatter)","note":"A first-response deadline and a resolution deadline measure different stages of the same incident."},{"id":"w008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ivrel-calibracion filtered out: no commitment signal (pure chatter)","note":"The same permitted dimensional tolerance is stated in millimetres and centimetres with an unchanged numeric value."},{"id":"w012","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ulnexa-acuerdos filtered out: no commitment signal (pure chatter)","note":"The same uptime commitment both includes and excludes planned maintenance from its measurement."},{"id":"w013","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #peldris-metering filtered out: no commitment signal (pure chatter)","note":"The two prices are equal after converting the quoted water-volume basis."},{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w016","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #elnovar-deliverables filtered out: no commitment signal (pure chatter)","note":"All files in the same export batch are required to use two different encodings."},{"id":"w017","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #dovrane-degustaciones filtered out: no commitment signal (pure chatter)","note":"The base daily limit explicitly allows signed waivers, and the higher count has such a waiver."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"1,440 minutes equals 12 hours, so both statements describe the same usable window.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w026","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #otharyn-show-control filtered out: no commitment signal (pure chatter)","note":"Publishing the same show requires two independent approvers in one policy and only one in the other."},{"id":"w028","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #kivrane-fixture-counts filtered out: no commitment signal (pure chatter)","note":"A per-run fixture limit and a simultaneous-run limit can both apply."},{"id":"w031","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #ivrel-evening-handover filtered out: no commitment signal (pure chatter)","note":"A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening."},{"id":"w033","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #qorlen-muestreo filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects the interval in their earlier sensor configuration message."},{"id":"w039","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #otharyn-audio filtered out: no commitment signal (pure chatter)","note":"Forty-eight kilohertz and forty-eight thousand samples per second express the same sampling rate."},{"id":"w043","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"Hardware pickup and account activation are different steps of the same deployment."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."},{"id":"w059","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"The key-collection window fits within the stated reservation hold."},{"id":"w060","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #tazvori-advance-order filtered out: no commitment signal (pure chatter)","note":"The same signed advance invoice has an identical numeric amount but two different required currencies."}]},{"run_utc":"2026-11-06T20:31:07+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":163.25,"llm_calls":57,"mean_latency_s":2.5115,"usage_reported":true,"prompt_tokens":96747,"completion_tokens":10035,"total_tokens":106782,"tp":12,"fp":0,"fn":8,"tn":40,"precision":1.0,"recall":0.6,"f1":0.7499999999999999,"matrix":{"contradiction:contradiction":12,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":7,"update:contradiction":0,"update:update":6,"update:compatible":0,"update:unrelated":4,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":6,"compatible:unrelated":9,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w002","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"An invited preview and general availability are separate milestones of the same release."},{"id":"w004","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-proofing filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own proof-copy count and withdraws the earlier number."},{"id":"w007","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #qorlen-restoration filtered out: no commitment signal (pure chatter)","note":"A first-response deadline and a resolution deadline measure different stages of the same incident."},{"id":"w008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ivrel-calibracion filtered out: no commitment signal (pure chatter)","note":"The same permitted dimensional tolerance is stated in millimetres and centimetres with an unchanged numeric value."},{"id":"w012","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ulnexa-acuerdos filtered out: no commitment signal (pure chatter)","note":"The same uptime commitment both includes and excludes planned maintenance from its measurement."},{"id":"w013","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #peldris-metering filtered out: no commitment signal (pure chatter)","note":"The two prices are equal after converting the quoted water-volume basis."},{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w016","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #elnovar-deliverables filtered out: no commitment signal (pure chatter)","note":"All files in the same export batch are required to use two different encodings."},{"id":"w017","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #dovrane-degustaciones filtered out: no commitment signal (pure chatter)","note":"The base daily limit explicitly allows signed waivers, and the higher count has such a waiver."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"1,440 minutes equals 12 hours, so both statements describe the same usable window.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w026","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #otharyn-show-control filtered out: no commitment signal (pure chatter)","note":"Publishing the same show requires two independent approvers in one policy and only one in the other."},{"id":"w028","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #kivrane-fixture-counts filtered out: no commitment signal (pure chatter)","note":"A per-run fixture limit and a simultaneous-run limit can both apply."},{"id":"w031","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #ivrel-evening-handover filtered out: no commitment signal (pure chatter)","note":"A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening."},{"id":"w033","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #qorlen-muestreo filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects the interval in their earlier sensor configuration message."},{"id":"w039","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #otharyn-audio filtered out: no commitment signal (pure chatter)","note":"Forty-eight kilohertz and forty-eight thousand samples per second express the same sampling rate."},{"id":"w043","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"Hardware pickup and account activation are different steps of the same deployment."},{"id":"w050","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The claims concern different subjects \u2014 the workshop's end time (17:30) versus its start time (16:00) \u2014 so they do not directly conflict.","note":"The same workshop starts at the same time but is booked for incompatible end times and durations."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."},{"id":"w059","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"The key-collection window fits within the stated reservation hold."},{"id":"w060","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #tazvori-advance-order filtered out: no commitment signal (pure chatter)","note":"The same signed advance invoice has an identical numeric amount but two different required currencies."}]},{"run_utc":"2026-11-06T20:33:52+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":111.875,"llm_calls":57,"mean_latency_s":1.6087,"usage_reported":true,"prompt_tokens":96770,"completion_tokens":9998,"total_tokens":106768,"tp":13,"fp":0,"fn":7,"tn":40,"precision":1.0,"recall":0.65,"f1":0.787878787878788,"matrix":{"contradiction:contradiction":13,"contradiction:update":0,"contradiction:compatible":1,"contradiction:unrelated":6,"update:contradiction":0,"update:update":6,"update:compatible":0,"update:unrelated":4,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":6,"compatible:unrelated":9,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":15},"errors":[{"id":"w002","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"An invited preview and general availability are separate milestones of the same release."},{"id":"w004","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-proofing filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own proof-copy count and withdraws the earlier number."},{"id":"w007","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #qorlen-restoration filtered out: no commitment signal (pure chatter)","note":"A first-response deadline and a resolution deadline measure different stages of the same incident."},{"id":"w008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ivrel-calibracion filtered out: no commitment signal (pure chatter)","note":"The same permitted dimensional tolerance is stated in millimetres and centimetres with an unchanged numeric value."},{"id":"w012","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ulnexa-acuerdos filtered out: no commitment signal (pure chatter)","note":"The same uptime commitment both includes and excludes planned maintenance from its measurement."},{"id":"w013","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #peldris-metering filtered out: no commitment signal (pure chatter)","note":"The two prices are equal after converting the quoted water-volume basis."},{"id":"w014","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #ravulon-riego filtered out: no commitment signal (pure chatter)","note":"The author corrects their own reminder time from evening to morning."},{"id":"w016","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #elnovar-deliverables filtered out: no commitment signal (pure chatter)","note":"All files in the same export batch are required to use two different encodings."},{"id":"w017","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #dovrane-degustaciones filtered out: no commitment signal (pure chatter)","note":"The base daily limit explicitly allows signed waivers, and the higher count has such a waiver."},{"id":"w023","label":"contradiction","predicted":"compatible","stage":"classification","confidence":0.9,"reason":"1,440 minutes equals 12 hours, so both statements describe the same usable window.","note":"The same opened resin has a twelve-hour usable life in one statement and a twenty-four-hour usable life in the other."},{"id":"w026","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #otharyn-show-control filtered out: no commitment signal (pure chatter)","note":"Publishing the same show requires two independent approvers in one policy and only one in the other."},{"id":"w028","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #kivrane-fixture-counts filtered out: no commitment signal (pure chatter)","note":"A per-run fixture limit and a simultaneous-run limit can both apply."},{"id":"w031","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #ivrel-evening-handover filtered out: no commitment signal (pure chatter)","note":"A response commitment restricted to staffed hours permits after-hours tickets to wait until the next opening."},{"id":"w033","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #qorlen-muestreo filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects the interval in their earlier sensor configuration message."},{"id":"w039","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #otharyn-audio filtered out: no commitment signal (pure chatter)","note":"Forty-eight kilohertz and forty-eight thousand samples per second express the same sampling rate."},{"id":"w043","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"Hardware pickup and account activation are different steps of the same deployment."},{"id":"w057","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #wexlune-draft-policy filtered out: no commitment signal (pure chatter)","note":"Deleting the same drafts is irreversible immediately in one policy and reversible for a mandatory thirty-day period in the other."},{"id":"w058","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #zenvora-informe filtered out: no commitment signal (pure chatter)","note":"The author explicitly corrects their own report-access instruction and retracts the unrestricted link."},{"id":"w059","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"The key-collection window fits within the stated reservation hold."},{"id":"w060","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #tazvori-advance-order filtered out: no commitment signal (pure chatter)","note":"The same signed advance invoice has an identical numeric amount but two different required currencies."}]}] -->
