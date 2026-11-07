# Splitbrain — v2 before and after the prefilter change

## Evaluation protocol and limits

- The first three live runs are **before** the prefilter change. The next three
  are **after** the frozen prefilter in `7ddd17a`; missing original-dataset
  cassettes were committed in `b117934` before opening reserve.
- Development: **v001-v050**, inspected while designing the prefilter. This half
  is **no longer unseen** to it. Reserve: **v051-v100**, whose pairs and detailed
  errors were first opened after the code and cassettes were committed. No
  prefilter changes followed reserve inspection or any of the new live runs.
- Disclosure: the initial full README read unintentionally exposed its pre-existing
  one-line summaries of reserve errors v060 and v070. They were not used to
  design the rules. Reserve was therefore not completely information-blind.
- Labels and dataset order are unchanged. For the first six runs only the prefilter
  changed; extraction prompts, matcher, classifier, threshold, and model configuration
  did not. The three runs in "After matcher change" also use the broader matcher
  described in that section.
- The mandated ID split is **not stratified**: development contains all **35
  contradictions and 15 updates**; reserve contains **25 compatible and 25
  unrelated pairs, with no contradictions**. Reserve recall cannot be estimated.
  Precision/F1 with a zero denominator are shown as `n/a`; the CLI's aggregate
  implementation uses zero for zero denominators. False positives, specificity,
  and four-label accuracy describe the reserve instead.
- Means are arithmetic means of the three runs in each phase. The original
  runs and every original error remain below. No v2 cassettes were recorded.
- Reproduce split metrics with
  `uv run python scripts/summarize_eval_splits.py --skip-runs 3`.
  The script reconstructs correct predictions from labels and mismatches from
  the stored errors, and checks all aggregate counts, metrics, and confusion
  matrix cells against the recorded run.
- Replay/scenario checks and the independent unit examples are documented in
  [`prefilter-validation.md`](prefilter-validation.md).

## Before/after interpretation

The mean live precision changes from **0.927** to
**0.849**, recall from **0.600** to
**0.857**, and F1 from **0.728** to
**0.853**. Recall improves, but the goal of retaining live
precision is **not achieved**: passing more pairs also exposes classifier false
positives. The original 44-pair replay retains precision 1.000, recall 0.889,
and F1 0.941 with every pair prediction unchanged.

In each of the three runs, label errors attributed to prefiltering fall from
30 before the change (19 development, 11 reserve) to 3 afterward (all in
development). This measures mislabeled pairs stopped by the prefilter, rather
than all filtered messages. Passing more pairs leaves matching and classification
as the main remaining sources of error.

Development four-label accuracy changes from 0.520
to 0.780. Reserve accuracy changes from
0.633 to 0.733,
while its mean false-positive count changes from 0.667
to 2.333 per 50 pairs. The reserve accuracy gain is
smaller, and its false-alarm rate worsens. There is **no reserve recall result**
to support a claim of improved recall on unseen contradictions. Remaining
prefilter false negatives in development are v007, v008, and v021; no words were
added after the frozen evaluation to target them or the reserve errors.

## Before prefilter change — original three live runs

- Latest run (UTC): 2026-11-06T08:10:26+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v2.jsonl` — 100 pairs (contradiction=35, update=15, compatible=25, unrelated=25)
- Language mix: en=70, es=18, mixed=12
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=485450, output=35684, total=521134 (mean per run: 161817 in / 11895 out / 173711 total; API dollar costs are not estimated).

### Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T07:59:57+00:00 | 0.913 | 0.600 | 0.724 | 21 / 2 / 14 / 63 | 42 | 100 | 287.94s | 2.525s | 161815 / 11892 / 173707 |
| 2 | 2026-11-06T08:04:47+00:00 | 0.955 | 0.600 | 0.737 | 21 / 1 / 14 / 64 | 42 | 100 | 336.36s | 3.009s | 161814 / 11896 / 173710 |
| 3 | 2026-11-06T08:10:26+00:00 | 0.913 | 0.600 | 0.724 | 21 / 2 / 14 / 63 | 43 | 100 | 363.69s | 3.257s | 161821 / 11896 / 173717 |
| **Mean** | — | **0.927** | **0.600** | **0.728** | 21.0 / 1.7 / 14.0 / 63.3 | 42.3 | 100.0 | 329.33s | 2.930s | 161817 / 11895 / 173711 |

### Run 1 — 2026-11-06T07:59:57+00:00

- Run (UTC): 2026-11-06T07:59:57+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 287.94s
- LLM calls: 100 (mean latency 2.525s per call)
- Token usage: input=161815, output=11892, total=173707 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.913 |
| recall | 0.600 |
| F1 | 0.724 |
| TP / FP / FN / TN | 21 / 2 / 14 / 63 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 21 | 0 | 0 | 14 |
| update | 1 | 5 | 0 | 9 |
| compatible | 1 | 0 | 7 | 17 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (42)

##### v002 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg versus 500 lb on the same scanner limit
- A (#warehouse, elena): The PalletScan limit is 500 kg per pallet for all warehouses.
- B (#qa, ivan): Engineering set PalletScan to reject anything over 500 lb per pallet everywhere.

##### v003 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: end-of-quarter GA versus a Q3 slip
- A (#product, yara): FleetLink general availability is locked for the end of quarter for every fleet customer.
- B (#fleet, mateo): FleetLink general availability slipped to Q3, we are not shipping at the end of quarter.

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #quality filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v010 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: 300 seats versus 30 seats in two languages
- A (#campus, sira): Piedmont University bought 300 DeskPass seats for the spring term, that is in the order form.
- B (#ventas, teo): El pedido de Piedmont University es de 30 asientos de DeskPass para el semestre de primavera.

##### v013 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: 98% versus 90% solar inverter availability
- A (#operaciones, yara): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, mateo): Operaciones solo puede garantizar un 90% de disponibilidad en los inversores solares de Nordvik Energi.

##### v017 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: drone restocking approved versus banned
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): Safety banned drone restocking at every Tundra Retail distribution centre until further notice.

##### v019 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: 20 kg versus 20 lb luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Operations set the Solstice Travel luggage allowance to 20 lb per passenger on every ferry route.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #billing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v023 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #energia filtered out: no commitment signal (pure chatter)
- Note: 8 hours versus 8 minutes of battery backup
- A (#energy, yara): Nordvik Energi microgrid batteries are rated for 8 hours of backup from day one.
- B (#energia, mateo): Las baterías de Nordvik Energi solo cubren 8 minutos de respaldo según la ficha técnica.

##### v025 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #operaciones filtered out: no commitment signal (pure chatter)
- Note: before end of quarter versus not until next year
- A (#ventas, ines): Confirmamos a Orchid Hotels que SmartLocker estará instalado antes de fin de trimestre.
- B (#operaciones, bruno): Instalaciones avisó que SmartLocker para Orchid Hotels no se instalará hasta el próximo año.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo types — general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 — so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v035 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #sistemas filtered out: no commitment signal (pure chatter)
- Note: 500 pages versus 50 pages printing quota
- A (#campus, ines): Piedmont University raised printing quotas to 500 pages per student each term.
- B (#sistemas, bruno): Piedmont University printing quotas are set to 50 pages per student each term.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject scope.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v039 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #research filtered out: no commitment signal (pure chatter)
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

##### v040 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #support filtered out: no commitment signal (pure chatter)
- Note: author corrects their own SLA number
- A (#partners, clara): Orchid Hotels SmartLocker incidents carry a four-hour response SLA from Monday.
- B (#support, hugo): Correction to my own post: the Orchid Hotels response SLA is two hours, not four.

##### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both claims set the same Maremar surcharge from March but in different currencies, EUR versus USD, which cannot both be the same amount.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v046 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: signed order supersedes the quoted seat count
- A (#campus, ines): Piedmont University bought 300 DeskPass seats for the spring term.
- B (#billing, bruno): Update from sales ops: the signed Piedmont University order is 350 DeskPass seats, superseding 300.

##### v047 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #almacen filtered out: no commitment signal (pure chatter)
- Note: operations widens the pilot to five warehouses
- A (#almacen, yara): El piloto de drone restocking con Boreal Foods arranca en tres almacenes.
- B (#operaciones, mateo): Aviso de operaciones: el piloto de Boreal Foods arranca en cinco almacenes, deja sin efecto los tres.

##### v048 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

##### v049 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v050 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

##### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

##### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v056 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #engineering filtered out: no commitment signal (pure chatter)
- Note: release feature plus an extra queue detail
- A (#product, lena): NovaPay offline mode is included in the January release for Tundra Retail terminals.
- B (#engineering, pavel): NovaPay offline mode also supports a 72-hour transaction queue for Tundra Retail terminals.

##### v057 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #fleet filtered out: no commitment signal (pure chatter)
- Note: pilot scope then wider rollout
- A (#fleet, aisha): The GreenRoute pilot with Ferrovia Rail covers two routes until fin de trimestre.
- B (#producto, diego): GreenRoute se amplía a todas las rutas de Ferrovia Rail en Q3, tras finalizar el piloto.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.86
- Reason: Both claims set the Cobalt Freight integration's hourly rate limit but give mutually exclusive values, 1200 vs 600 requests per hour.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

##### v062 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: base seats plus an optional extension
- A (#campus, ines): Piedmont University compró 300 asientos de DeskPass para el semestre de primavera.
- B (#ventas, bruno): Piedmont University puede ampliar DeskPass con 50 asientos adicionales bajo pedido desde abril.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #pricing filtered out: no commitment signal (pure chatter)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v068 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

##### v069 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #producto filtered out: no commitment signal (pure chatter)
- Note: beta next Friday and GA at end of quarter
- A (#almacen, rosa): La beta de PalletScan para Casa Verde abre el próximo viernes en un almacén.
- B (#producto, omar): PalletScan llega a disponibilidad general para Casa Verde a fin de trimestre, después de la beta.

##### v071 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg written as 0.5 tonnes
- A (#warehouse, elena): PalletScan rejects pallets over 500 kg in every warehouse.
- B (#qa, ivan): The PalletScan threshold is written as 0.5 tonnes per pallet in the configuration guide.

##### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Run 2 — 2026-11-06T08:04:47+00:00

- Run (UTC): 2026-11-06T08:04:47+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 336.36s
- LLM calls: 100 (mean latency 3.009s per call)
- Token usage: input=161814, output=11896, total=173710 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.955 |
| recall | 0.600 |
| F1 | 0.737 |
| TP / FP / FN / TN | 21 / 1 / 14 / 64 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 21 | 0 | 0 | 14 |
| update | 1 | 5 | 0 | 9 |
| compatible | 0 | 0 | 7 | 18 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (42)

##### v002 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg versus 500 lb on the same scanner limit
- A (#warehouse, elena): The PalletScan limit is 500 kg per pallet for all warehouses.
- B (#qa, ivan): Engineering set PalletScan to reject anything over 500 lb per pallet everywhere.

##### v003 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: end-of-quarter GA versus a Q3 slip
- A (#product, yara): FleetLink general availability is locked for the end of quarter for every fleet customer.
- B (#fleet, mateo): FleetLink general availability slipped to Q3, we are not shipping at the end of quarter.

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #quality filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v010 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: 300 seats versus 30 seats in two languages
- A (#campus, sira): Piedmont University bought 300 DeskPass seats for the spring term, that is in the order form.
- B (#ventas, teo): El pedido de Piedmont University es de 30 asientos de DeskPass para el semestre de primavera.

##### v013 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: 98% versus 90% solar inverter availability
- A (#operaciones, yara): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, mateo): Operaciones solo puede garantizar un 90% de disponibilidad en los inversores solares de Nordvik Energi.

##### v017 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: drone restocking approved versus banned
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): Safety banned drone restocking at every Tundra Retail distribution centre until further notice.

##### v019 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: 20 kg versus 20 lb luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Operations set the Solstice Travel luggage allowance to 20 lb per passenger on every ferry route.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #billing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v023 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #energia filtered out: no commitment signal (pure chatter)
- Note: 8 hours versus 8 minutes of battery backup
- A (#energy, yara): Nordvik Energi microgrid batteries are rated for 8 hours of backup from day one.
- B (#energia, mateo): Las baterías de Nordvik Energi solo cubren 8 minutos de respaldo según la ficha técnica.

##### v025 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #operaciones filtered out: no commitment signal (pure chatter)
- Note: before end of quarter versus not until next year
- A (#ventas, ines): Confirmamos a Orchid Hotels que SmartLocker estará instalado antes de fin de trimestre.
- B (#operaciones, bruno): Instalaciones avisó que SmartLocker para Orchid Hotels no se instalará hasta el próximo año.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo types — general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 — so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v035 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #sistemas filtered out: no commitment signal (pure chatter)
- Note: 500 pages versus 50 pages printing quota
- A (#campus, ines): Piedmont University raised printing quotas to 500 pages per student each term.
- B (#sistemas, bruno): Piedmont University printing quotas are set to 50 pages per student each term.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they address different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v039 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #research filtered out: no commitment signal (pure chatter)
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

##### v040 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #support filtered out: no commitment signal (pure chatter)
- Note: author corrects their own SLA number
- A (#partners, clara): Orchid Hotels SmartLocker incidents carry a four-hour response SLA from Monday.
- B (#support, hugo): Correction to my own post: the Orchid Hotels response SLA is two hours, not four.

##### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is a general scope while the December commitment is specific to Tundra Retail, so the scopes differ.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v046 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: signed order supersedes the quoted seat count
- A (#campus, ines): Piedmont University bought 300 DeskPass seats for the spring term.
- B (#billing, bruno): Update from sales ops: the signed Piedmont University order is 350 DeskPass seats, superseding 300.

##### v047 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #almacen filtered out: no commitment signal (pure chatter)
- Note: operations widens the pilot to five warehouses
- A (#almacen, yara): El piloto de drone restocking con Boreal Foods arranca en tres almacenes.
- B (#operaciones, mateo): Aviso de operaciones: el piloto de Boreal Foods arranca en cinco almacenes, deja sin efecto los tres.

##### v048 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

##### v049 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v050 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

##### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

##### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v056 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #engineering filtered out: no commitment signal (pure chatter)
- Note: release feature plus an extra queue detail
- A (#product, lena): NovaPay offline mode is included in the January release for Tundra Retail terminals.
- B (#engineering, pavel): NovaPay offline mode also supports a 72-hour transaction queue for Tundra Retail terminals.

##### v057 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #fleet filtered out: no commitment signal (pure chatter)
- Note: pilot scope then wider rollout
- A (#fleet, aisha): The GreenRoute pilot with Ferrovia Rail covers two routes until fin de trimestre.
- B (#producto, diego): GreenRoute se amplía a todas las rutas de Ferrovia Rail en Q3, tras finalizar el piloto.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The 1200/hour figure is an approved exception for the holiday integration, while 600/hour is the standard customs broker API policy, so both can hold.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

##### v062 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: base seats plus an optional extension
- A (#campus, ines): Piedmont University compró 300 asientos de DeskPass para el semestre de primavera.
- B (#ventas, bruno): Piedmont University puede ampliar DeskPass con 50 asientos adicionales bajo pedido desde abril.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #pricing filtered out: no commitment signal (pure chatter)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v068 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

##### v069 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #producto filtered out: no commitment signal (pure chatter)
- Note: beta next Friday and GA at end of quarter
- A (#almacen, rosa): La beta de PalletScan para Casa Verde abre el próximo viernes en un almacén.
- B (#producto, omar): PalletScan llega a disponibilidad general para Casa Verde a fin de trimestre, después de la beta.

##### v071 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg written as 0.5 tonnes
- A (#warehouse, elena): PalletScan rejects pallets over 500 kg in every warehouse.
- B (#qa, ivan): The PalletScan threshold is written as 0.5 tonnes per pallet in the configuration guide.

##### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Run 3 — 2026-11-06T08:10:26+00:00

- Run (UTC): 2026-11-06T08:10:26+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 363.69s
- LLM calls: 100 (mean latency 3.257s per call)
- Token usage: input=161821, output=11896, total=173717 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.913 |
| recall | 0.600 |
| F1 | 0.724 |
| TP / FP / FN / TN | 21 / 2 / 14 / 63 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 21 | 0 | 0 | 14 |
| update | 1 | 5 | 0 | 9 |
| compatible | 1 | 0 | 6 | 18 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (43)

##### v002 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg versus 500 lb on the same scanner limit
- A (#warehouse, elena): The PalletScan limit is 500 kg per pallet for all warehouses.
- B (#qa, ivan): Engineering set PalletScan to reject anything over 500 lb per pallet everywhere.

##### v003 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: end-of-quarter GA versus a Q3 slip
- A (#product, yara): FleetLink general availability is locked for the end of quarter for every fleet customer.
- B (#fleet, mateo): FleetLink general availability slipped to Q3, we are not shipping at the end of quarter.

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #quality filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v010 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: 300 seats versus 30 seats in two languages
- A (#campus, sira): Piedmont University bought 300 DeskPass seats for the spring term, that is in the order form.
- B (#ventas, teo): El pedido de Piedmont University es de 30 asientos de DeskPass para el semestre de primavera.

##### v013 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: 98% versus 90% solar inverter availability
- A (#operaciones, yara): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, mateo): Operaciones solo puede garantizar un 90% de disponibilidad en los inversores solares de Nordvik Energi.

##### v017 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: drone restocking approved versus banned
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): Safety banned drone restocking at every Tundra Retail distribution centre until further notice.

##### v019 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: 20 kg versus 20 lb luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Operations set the Solstice Travel luggage allowance to 20 lb per passenger on every ferry route.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #billing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v023 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #energia filtered out: no commitment signal (pure chatter)
- Note: 8 hours versus 8 minutes of battery backup
- A (#energy, yara): Nordvik Energi microgrid batteries are rated for 8 hours of backup from day one.
- B (#energia, mateo): Las baterías de Nordvik Energi solo cubren 8 minutos de respaldo según la ficha técnica.

##### v025 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #operaciones filtered out: no commitment signal (pure chatter)
- Note: before end of quarter versus not until next year
- A (#ventas, ines): Confirmamos a Orchid Hotels que SmartLocker estará instalado antes de fin de trimestre.
- B (#operaciones, bruno): Instalaciones avisó que SmartLocker para Orchid Hotels no se instalará hasta el próximo año.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The 50,000 EUR limit applies specifically to refrigerated containers, a narrower scope than the general 5,000 EUR per-container limit, so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v035 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #sistemas filtered out: no commitment signal (pure chatter)
- Note: 500 pages versus 50 pages printing quota
- A (#campus, ines): Piedmont University raised printing quotas to 500 pages per student each term.
- B (#sistemas, bruno): Piedmont University printing quotas are set to 50 pages per student each term.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v039 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #research filtered out: no commitment signal (pure chatter)
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

##### v040 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #support filtered out: no commitment signal (pure chatter)
- Note: author corrects their own SLA number
- A (#partners, clara): Orchid Hotels SmartLocker incidents carry a four-hour response SLA from Monday.
- B (#support, hugo): Correction to my own post: the Orchid Hotels response SLA is two hours, not four.

##### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v046 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: signed order supersedes the quoted seat count
- A (#campus, ines): Piedmont University bought 300 DeskPass seats for the spring term.
- B (#billing, bruno): Update from sales ops: the signed Piedmont University order is 350 DeskPass seats, superseding 300.

##### v047 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #almacen filtered out: no commitment signal (pure chatter)
- Note: operations widens the pilot to five warehouses
- A (#almacen, yara): El piloto de drone restocking con Boreal Foods arranca en tres almacenes.
- B (#operaciones, mateo): Aviso de operaciones: el piloto de Boreal Foods arranca en cinco almacenes, deja sin efecto los tres.

##### v048 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

##### v049 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v050 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

##### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

##### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v056 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #engineering filtered out: no commitment signal (pure chatter)
- Note: release feature plus an extra queue detail
- A (#product, lena): NovaPay offline mode is included in the January release for Tundra Retail terminals.
- B (#engineering, pavel): NovaPay offline mode also supports a 72-hour transaction queue for Tundra Retail terminals.

##### v057 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #fleet filtered out: no commitment signal (pure chatter)
- Note: pilot scope then wider rollout
- A (#fleet, aisha): The GreenRoute pilot with Ferrovia Rail covers two routes until fin de trimestre.
- B (#producto, diego): GreenRoute se amplía a todas las rutas de Ferrovia Rail en Q3, tras finalizar el piloto.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

##### v062 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: base seats plus an optional extension
- A (#campus, ines): Piedmont University compró 300 asientos de DeskPass para el semestre de primavera.
- B (#ventas, bruno): Piedmont University puede ampliar DeskPass con 50 asientos adicionales bajo pedido desde abril.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #pricing filtered out: no commitment signal (pure chatter)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v068 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

##### v069 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #producto filtered out: no commitment signal (pure chatter)
- Note: beta next Friday and GA at end of quarter
- A (#almacen, rosa): La beta de PalletScan para Casa Verde abre el próximo viernes en un almacén.
- B (#producto, omar): PalletScan llega a disponibilidad general para Casa Verde a fin de trimestre, después de la beta.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v071 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg written as 0.5 tonnes
- A (#warehouse, elena): PalletScan rejects pallets over 500 kg in every warehouse.
- B (#qa, ivan): The PalletScan threshold is written as 0.5 tonnes per pallet in the configuration guide.

##### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

## After prefilter change — three new live runs

- Latest run (UTC): 2026-11-06T20:00:35+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v2.jsonl` — 100 pairs (contradiction=35, update=15, compatible=25, unrelated=25)
- Language mix: en=70, es=18, mixed=12
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=748500, output=54781, total=803281 (mean per run: 249500 in / 18260 out / 267760 total; API dollar costs are not estimated).

### Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T19:48:53+00:00 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 25 | 154 | 294.81s | 1.557s | 248852 / 18284 / 267136 |
| 2 | 2026-11-06T19:53:49+00:00 | 0.833 | 0.857 | 0.845 | 30 / 6 / 5 / 59 | 24 | 155 | 404.84s | 2.256s | 250786 / 18258 / 269044 |
| 3 | 2026-11-06T20:00:35+00:00 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 24 | 154 | 323.50s | 1.744s | 248862 / 18239 / 267101 |
| **Mean** | — | **0.849** | **0.857** | **0.853** | 30.0 / 5.3 / 5.0 / 59.7 | 24.3 | 154.3 | 341.05s | 1.853s | 249500 / 18260 / 267760 |

### Run 1 — 2026-11-06T19:48:53+00:00

- Run (UTC): 2026-11-06T19:48:53+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 294.81s
- LLM calls: 154 (mean latency 1.557s per call)
- Token usage: input=248852, output=18284, total=267136 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.857 |
| recall | 0.857 |
| F1 | 0.857 |
| TP / FP / FN / TN | 30 / 5 / 5 / 60 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 30 | 0 | 0 | 5 |
| update | 3 | 9 | 0 | 3 |
| compatible | 2 | 0 | 11 | 12 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (25)

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #legal filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #pricing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo scopes: general containers at EUR 5,000 versus refrigerated containers at EUR 50,000.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is a correction of a general pallet price while the other sets a price specifically for refrigerated pallets, so they concern different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v042 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Engineering cancelled the December slot for NovaPay offline mode while product still commits it to the December release for Tundra Retail.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v048 — label `update`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

##### v049 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v050 — label `update`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

##### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

##### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for each Cobalt Freight integration, so they can coexist.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v068 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Run 2 — 2026-11-06T19:53:49+00:00

- Run (UTC): 2026-11-06T19:53:49+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 404.84s
- LLM calls: 155 (mean latency 2.256s per call)
- Token usage: input=250786, output=18258, total=269044 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.833 |
| recall | 0.857 |
| F1 | 0.845 |
| TP / FP / FN / TN | 30 / 6 / 5 / 59 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 30 | 0 | 0 | 5 |
| update | 3 | 9 | 0 | 3 |
| compatible | 3 | 0 | 12 | 10 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (24)

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #legal filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #pricing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo types, general containers versus refrigerated containers, so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is a general pallet price correction while the other concerns specifically refrigerated pallets, so they are different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v042 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Engineering cancelled the December slot for NovaPay offline mode while product still commits it to the December release for Tundra Retail.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, 250 EUR versus 250 USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v048 — label `update`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

##### v049 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v050 — label `update`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

##### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

##### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.86
- Reason: Both claims set the Cobalt Freight integration's hourly rate limit but give mutually exclusive values, 1200 vs 600 requests per hour.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing says agencies get a 30-day post-quarter waiver before the Solstice Travel fee applies, while pricing says the fee takes effect at end of quarter for all agencies.
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v068 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Run 3 — 2026-11-06T20:00:35+00:00

- Run (UTC): 2026-11-06T20:00:35+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 323.50s
- LLM calls: 154 (mean latency 1.744s per call)
- Token usage: input=248862, output=18239, total=267101 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.857 |
| recall | 0.857 |
| F1 | 0.857 |
| TP / FP / FN / TN | 30 / 5 / 5 / 60 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 30 | 0 | 0 | 5 |
| update | 3 | 9 | 0 | 3 |
| compatible | 2 | 0 | 12 | 11 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (24)

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #legal filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #pricing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo scopes: general containers at EUR 5,000 versus refrigerated containers at EUR 50,000.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v042 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Engineering cancelled the December slot for NovaPay offline mode while product still commits it to the December release for Tundra Retail.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, 250 EUR versus 250 USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v048 — label `update`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

##### v049 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v050 — label `update`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

##### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

##### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.78
- Reason: Both state a specific hourly rate limit for the same Cobalt Freight integration, 1200 vs 600, which cannot both be the effective limit.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v068 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

## Metrics by development/reserve split

### Before prefilter change

| run | split | N / positives | precision | recall | F1 | TP / FP / FN / TN | label errors | label accuracy | specificity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | all | 100 / 35 | 0.913 | 0.600 | 0.724 | 21 / 2 / 14 / 63 | 42 | 0.580 | 0.969 |
| 1 | development | 50 / 35 | 0.955 | 0.600 | 0.737 | 21 / 1 / 14 / 14 | 24 | 0.520 | 0.933 |
| 1 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 1 / 0 / 49 | 18 | 0.640 | 0.980 |
| 2 | all | 100 / 35 | 0.955 | 0.600 | 0.737 | 21 / 1 / 14 / 64 | 42 | 0.580 | 0.985 |
| 2 | development | 50 / 35 | 0.955 | 0.600 | 0.737 | 21 / 1 / 14 / 14 | 24 | 0.520 | 0.933 |
| 2 | reserve | 50 / 0 | n/a | n/a | n/a | 0 / 0 / 0 / 50 | 18 | 0.640 | 1.000 |
| 3 | all | 100 / 35 | 0.913 | 0.600 | 0.724 | 21 / 2 / 14 / 63 | 43 | 0.570 | 0.969 |
| 3 | development | 50 / 35 | 0.955 | 0.600 | 0.737 | 21 / 1 / 14 / 14 | 24 | 0.520 | 0.933 |
| 3 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 1 / 0 / 49 | 19 | 0.620 | 0.980 |
| **Mean** | **all** | 100 / 35 | 0.927 | 0.600 | 0.728 | 21.0 / 1.7 / 14.0 / 63.3 | 42.3 | 0.577 | 0.974 |
| **Mean** | **development** | 50 / 35 | 0.955 | 0.600 | 0.737 | 21.0 / 1.0 / 14.0 / 14.0 | 24.0 | 0.520 | 0.933 |
| **Mean** | **reserve** | 50 / 0 | n/a | n/a | n/a | 0.0 / 0.7 / 0.0 / 49.3 | 18.3 | 0.633 | 0.987 |

### After prefilter change

| run | split | N / positives | precision | recall | F1 | TP / FP / FN / TN | label errors | label accuracy | specificity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | all | 100 / 35 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 25 | 0.750 | 0.923 |
| 1 | development | 50 / 35 | 0.909 | 0.857 | 0.882 | 30 / 3 / 5 / 12 | 11 | 0.780 | 0.800 |
| 1 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 2 / 0 / 48 | 14 | 0.720 | 0.960 |
| 2 | all | 100 / 35 | 0.833 | 0.857 | 0.845 | 30 / 6 / 5 / 59 | 24 | 0.760 | 0.908 |
| 2 | development | 50 / 35 | 0.909 | 0.857 | 0.882 | 30 / 3 / 5 / 12 | 11 | 0.780 | 0.800 |
| 2 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 3 / 0 / 47 | 13 | 0.740 | 0.940 |
| 3 | all | 100 / 35 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 24 | 0.760 | 0.923 |
| 3 | development | 50 / 35 | 0.909 | 0.857 | 0.882 | 30 / 3 / 5 / 12 | 11 | 0.780 | 0.800 |
| 3 | reserve | 50 / 0 | 0.000 | n/a | 0.000 | 0 / 2 / 0 / 48 | 13 | 0.740 | 0.960 |
| **Mean** | **all** | 100 / 35 | 0.849 | 0.857 | 0.853 | 30.0 / 5.3 / 5.0 / 59.7 | 24.3 | 0.757 | 0.918 |
| **Mean** | **development** | 50 / 35 | 0.909 | 0.857 | 0.882 | 30.0 / 3.0 / 5.0 / 12.0 | 11.0 | 0.780 | 0.800 |
| **Mean** | **reserve** | 50 / 0 | 0.000 | n/a | 0.000 | 0.0 / 2.3 / 0.0 / 47.7 | 13.3 | 0.733 | 0.953 |

`n/a` means a zero denominator; reserve has no actual contradictions.

## After matcher change — three new live runs

- Latest run (UTC): 2026-11-07T00:16:00+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v2.jsonl` — 100 pairs (contradiction=35, update=15, compatible=25, unrelated=25)
- Language mix: en=70, es=18, mixed=12
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=809764, output=56205, total=865969 (mean per run: 269921 in / 18735 out / 288656 total; API dollar costs are not estimated).

The matcher no longer requires an exact `subject_key`. It compares canonical key tokens, subject words, scope, distinctive values and message text, and it only accepts a finer scope when the shared word names the subject. The three runs below use the same dataset, model and pipeline as the previous six runs.

### Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 2026-11-07T00:06:53+00:00 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 19 | 165 | 267.09s | 1.261s | 269919 / 18730 / 288649 |
| 8 | 2026-11-07T00:11:35+00:00 | 0.833 | 0.857 | 0.845 | 30 / 6 / 5 / 59 | 19 | 165 | 252.83s | 1.175s | 269929 / 18747 / 288676 |
| 9 | 2026-11-07T00:16:00+00:00 | 0.857 | 0.857 | 0.857 | 30 / 5 / 5 / 60 | 19 | 165 | 266.66s | 1.244s | 269916 / 18728 / 288644 |
| **Mean** | — | **0.849** | **0.857** | **0.853** | 30.0 / 5.3 / 5.0 / 59.7 | 19.0 | 165.0 | 262.19s | 1.227s | 269921 / 18735 / 288656 |

### Matching errors and false alarms

- Matching-stage errors fall from 14/13/14 in the previous three runs to 3/3/3. The remaining three are v020 (`different scope`), v063 (`different subject`) and v073 (`different subject`).
- Errors whose reason is `matcher rejected the pair (different subject)` fall from 11/10/10 to 2/2/2 per run (v063 and v073).
- v039 is a new false alarm in all three runs. v060 no longer appears as a false alarm, and v042 appears only in run 8. The mean false-positive count stays at 5.33 per run, so mean precision remains 0.849.
- Recall stays at 0.857 (30/35 contradictions). The five false negatives are unchanged: v007, v008 and v021 (prefilter), v020 (matching) and v032 (classification).

### Run 7 — 2026-11-07T00:06:53+00:00

- Run (UTC): 2026-11-07T00:06:53+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 267.09s
- LLM calls: 165 (mean latency 1.261s per call)
- Token usage: input=269919, output=18730, total=288649 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.857 |
| recall | 0.857 |
| F1 | 0.857 |
| TP / FP / FN / TN | 30 / 5 / 5 / 60 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 30 | 0 | 0 | 5 |
| update | 3 | 10 | 0 | 2 |
| compatible | 2 | 0 | 16 | 7 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (19)

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #legal filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #pricing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The two limits apply to different cargo scopes — general containers vs refrigerated containers — so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v039 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Platform says siloTemp retention was reduced to 6 months globally today, while research asserts 18 months for grain customers, and both are active now.
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

##### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is a global scope while the December commitment is specific to Tundra Retail, so they concern different scopes.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both claims set the same Maremar surcharge starting in March but in different currencies, EUR versus USD, which cannot both be the same amount.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v049 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The Thursday schedule is an approved exception for the Valparaíso clinic, a narrower scope than the general Tuesday policy for all Vela Health clinics.
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is about general data retention policy with a maintenance exclusion, the other about siloTemp sensor reading retention, which are different subjects.
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The 200-kit limit applies to Harborview Clinic generally while the 400-kit exception is scoped specifically to Harborview Clinic downtown, a different scope.
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: One claim sets a coverage limit while the other excludes a specific peril, so they address different subjects and can both hold.
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Run 8 — 2026-11-07T00:11:35+00:00

- Run (UTC): 2026-11-07T00:11:35+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 252.83s
- LLM calls: 165 (mean latency 1.175s per call)
- Token usage: input=269929, output=18747, total=288676 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.833 |
| recall | 0.857 |
| F1 | 0.845 |
| TP / FP / FN / TN | 30 / 6 / 5 / 59 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 30 | 0 | 0 | 5 |
| update | 4 | 10 | 0 | 1 |
| compatible | 2 | 0 | 16 | 7 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (19)

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #legal filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #pricing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The two limits apply to different cargo scopes — general containers vs refrigerated containers — so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v039 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Platform says siloTemp retention was cut to 6 months globally today, while research asserts 18-month retention for grain customers, which cannot both hold now.
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

##### v042 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Engineering cancelled the December slot for NovaPay offline mode while product committed it to the December release for Tundra Retail.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both claims set the same Maremar surcharge starting in March but in different currencies, EUR versus USD, which cannot both be the same amount.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v049 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The Thursday schedule is an approved exception for the Valparaíso clinic, a narrower scope than the general Tuesday policy for all Vela Health clinics.
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is about general data retention policy with a maintenance exclusion, the other about siloTemp sensor reading retention, which are different subjects.
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The 200-kit limit applies to Harborview Clinic generally while the 400-kit exception is a signed exception for the specific Harborview Clinic downtown site.
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: One claim sets a coverage limit while the other excludes a specific peril, so they address different subjects and can both hold.
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Run 9 — 2026-11-07T00:16:00+00:00

- Run (UTC): 2026-11-07T00:16:00+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 266.66s
- LLM calls: 165 (mean latency 1.244s per call)
- Token usage: input=269916, output=18728, total=288644 (costs are not estimated)

#### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.857 |
| recall | 0.857 |
| F1 | 0.857 |
| TP / FP / FN / TN | 30 / 5 / 5 / 60 |

#### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 30 | 0 | 0 | 5 |
| update | 3 | 10 | 0 | 2 |
| compatible | 2 | 0 | 16 | 7 |
| unrelated | 0 | 0 | 0 | 25 |

#### Errors (19)

##### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

##### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #legal filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

##### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

##### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #pricing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

##### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo scopes: general containers at EUR 5,000 versus refrigerated containers at EUR 50,000.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

##### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

##### v039 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Platform says siloTemp retention was cut to 6 months globally today, while research asserts 18-month retention for grain customers, which cannot both hold now.
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

##### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is a global scope while the December commitment is specific to Tundra Retail, so they concern different scopes.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

##### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both claims set the same Maremar surcharge starting in March but in different currencies, EUR versus USD, which cannot both be the same amount.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

##### v049 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

##### v055 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.90
- Reason: The Thursday schedule is an approved exception for the Valparaíso clinic, a narrower scope than the general Tuesday policy for all Vela Health clinics.
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

##### v058 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is about general data retention policy with a maintenance exclusion, the other about siloTemp sensor reading retention, which are different subjects.
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

##### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

##### v063 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

##### v065 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

##### v067 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The 200-kit limit applies to Harborview Clinic generally while the 400-kit exception is scoped specifically to Harborview Clinic downtown, a different scope.
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

##### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

##### v073 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

##### v074 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: One claim sets a coverage limit while the other excludes a specific peril, so they address different subjects and can both hold.
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

### Known limits proposal

If the refunds key variation is considered resolved, replace the README bullet "Live extraction can vary across runs" with:

> **Live extraction can vary across runs.** With a live model, extracted fields are not guaranteed to be identical on every call. The matcher no longer depends on an exact `subject_key`: it also compares subject words, scope, distinctive values and message text, so a `refunds`/`approval-threshold` key difference still forms the pair. Replay mode is deterministic, which is why `eval` uses it by default and `demo` uses it whenever no API key is set.
<!-- splitbrain-live-runs [{"run_utc":"2026-11-06T07:59:57+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":287.937,"llm_calls":100,"mean_latency_s":2.5253,"usage_reported":true,"prompt_tokens":161815,"completion_tokens":11892,"total_tokens":173707,"tp":21,"fp":2,"fn":14,"tn":63,"precision":0.9130434782608695,"recall":0.6,"f1":0.7241379310344828,"matrix":{"contradiction:contradiction":21,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":14,"update:contradiction":1,"update:update":5,"update:compatible":0,"update:unrelated":9,"compatible:contradiction":1,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":17,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v002","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg versus 500 lb on the same scanner limit"},{"id":"v003","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"end-of-quarter GA versus a Q3 slip"},{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #quality filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v010","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"300 seats versus 30 seats in two languages"},{"id":"v013","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"98% versus 90% solar inverter availability"},{"id":"v017","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"drone restocking approved versus banned"},{"id":"v019","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"20 kg versus 20 lb luggage allowance"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #billing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v023","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #energia filtered out: no commitment signal (pure chatter)","note":"8 hours versus 8 minutes of battery backup"},{"id":"v025","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #operaciones filtered out: no commitment signal (pure chatter)","note":"before end of quarter versus not until next year"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo types \u2014 general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 \u2014 so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v035","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #sistemas filtered out: no commitment signal (pure chatter)","note":"500 pages versus 50 pages printing quota"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject scope.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #research filtered out: no commitment signal (pure chatter)","note":"retention policy replaces the old figure"},{"id":"v040","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #support filtered out: no commitment signal (pure chatter)","note":"author corrects their own SLA number"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both claims set the same Maremar surcharge from March but in different currencies, EUR versus USD, which cannot both be the same amount.","note":"author corrects the surcharge currency"},{"id":"v046","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"signed order supersedes the quoted seat count"},{"id":"v047","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #almacen filtered out: no commitment signal (pure chatter)","note":"operations widens the pilot to five warehouses"},{"id":"v048","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v056","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #engineering filtered out: no commitment signal (pure chatter)","note":"release feature plus an extra queue detail"},{"id":"v057","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #fleet filtered out: no commitment signal (pure chatter)","note":"pilot scope then wider rollout"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.86,"reason":"Both claims set the Cobalt Freight integration's hourly rate limit but give mutually exclusive values, 1200 vs 600 requests per hour.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v062","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"base seats plus an optional extension"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #pricing filtered out: no commitment signal (pure chatter)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"residency plus an encryption requirement"},{"id":"v069","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #producto filtered out: no commitment signal (pure chatter)","note":"beta next Friday and GA at end of quarter"},{"id":"v071","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg written as 0.5 tonnes"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T08:04:47+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":336.36,"llm_calls":100,"mean_latency_s":3.0085,"usage_reported":true,"prompt_tokens":161814,"completion_tokens":11896,"total_tokens":173710,"tp":21,"fp":1,"fn":14,"tn":64,"precision":0.9545454545454546,"recall":0.6,"f1":0.7368421052631579,"matrix":{"contradiction:contradiction":21,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":14,"update:contradiction":1,"update:update":5,"update:compatible":0,"update:unrelated":9,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":18,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v002","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg versus 500 lb on the same scanner limit"},{"id":"v003","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"end-of-quarter GA versus a Q3 slip"},{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #quality filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v010","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"300 seats versus 30 seats in two languages"},{"id":"v013","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"98% versus 90% solar inverter availability"},{"id":"v017","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"drone restocking approved versus banned"},{"id":"v019","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"20 kg versus 20 lb luggage allowance"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #billing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v023","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #energia filtered out: no commitment signal (pure chatter)","note":"8 hours versus 8 minutes of battery backup"},{"id":"v025","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #operaciones filtered out: no commitment signal (pure chatter)","note":"before end of quarter versus not until next year"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo types \u2014 general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 \u2014 so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v035","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #sistemas filtered out: no commitment signal (pure chatter)","note":"500 pages versus 50 pages printing quota"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they address different subjects.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #research filtered out: no commitment signal (pure chatter)","note":"retention policy replaces the old figure"},{"id":"v040","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #support filtered out: no commitment signal (pure chatter)","note":"author corrects their own SLA number"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is a general scope while the December commitment is specific to Tundra Retail, so the scopes differ.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.","note":"author corrects the surcharge currency"},{"id":"v046","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"signed order supersedes the quoted seat count"},{"id":"v047","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #almacen filtered out: no commitment signal (pure chatter)","note":"operations widens the pilot to five warehouses"},{"id":"v048","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v056","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #engineering filtered out: no commitment signal (pure chatter)","note":"release feature plus an extra queue detail"},{"id":"v057","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #fleet filtered out: no commitment signal (pure chatter)","note":"pilot scope then wider rollout"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The 1200/hour figure is an approved exception for the holiday integration, while 600/hour is the standard customs broker API policy, so both can hold.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v062","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"base seats plus an optional extension"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #pricing filtered out: no commitment signal (pure chatter)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"residency plus an encryption requirement"},{"id":"v069","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #producto filtered out: no commitment signal (pure chatter)","note":"beta next Friday and GA at end of quarter"},{"id":"v071","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg written as 0.5 tonnes"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T08:10:26+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":363.687,"llm_calls":100,"mean_latency_s":3.2567,"usage_reported":true,"prompt_tokens":161821,"completion_tokens":11896,"total_tokens":173717,"tp":21,"fp":2,"fn":14,"tn":63,"precision":0.9130434782608695,"recall":0.6,"f1":0.7241379310344828,"matrix":{"contradiction:contradiction":21,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":14,"update:contradiction":1,"update:update":5,"update:compatible":0,"update:unrelated":9,"compatible:contradiction":1,"compatible:update":0,"compatible:compatible":6,"compatible:unrelated":18,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v002","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg versus 500 lb on the same scanner limit"},{"id":"v003","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"end-of-quarter GA versus a Q3 slip"},{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #quality filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v010","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"300 seats versus 30 seats in two languages"},{"id":"v013","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"98% versus 90% solar inverter availability"},{"id":"v017","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"drone restocking approved versus banned"},{"id":"v019","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"20 kg versus 20 lb luggage allowance"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #billing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v023","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #energia filtered out: no commitment signal (pure chatter)","note":"8 hours versus 8 minutes of battery backup"},{"id":"v025","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #operaciones filtered out: no commitment signal (pure chatter)","note":"before end of quarter versus not until next year"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The 50,000 EUR limit applies specifically to refrigerated containers, a narrower scope than the general 5,000 EUR per-container limit, so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v035","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #sistemas filtered out: no commitment signal (pure chatter)","note":"500 pages versus 50 pages printing quota"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #research filtered out: no commitment signal (pure chatter)","note":"retention policy replaces the old figure"},{"id":"v040","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #support filtered out: no commitment signal (pure chatter)","note":"author corrects their own SLA number"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.","note":"author corrects the surcharge currency"},{"id":"v046","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"signed order supersedes the quoted seat count"},{"id":"v047","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #almacen filtered out: no commitment signal (pure chatter)","note":"operations widens the pilot to five warehouses"},{"id":"v048","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v056","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #engineering filtered out: no commitment signal (pure chatter)","note":"release feature plus an extra queue detail"},{"id":"v057","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #fleet filtered out: no commitment signal (pure chatter)","note":"pilot scope then wider rollout"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v062","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"base seats plus an optional extension"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #pricing filtered out: no commitment signal (pure chatter)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"residency plus an encryption requirement"},{"id":"v069","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #producto filtered out: no commitment signal (pure chatter)","note":"beta next Friday and GA at end of quarter"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v071","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg written as 0.5 tonnes"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T19:48:53+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":294.812,"llm_calls":154,"mean_latency_s":1.5574,"usage_reported":true,"prompt_tokens":248852,"completion_tokens":18284,"total_tokens":267136,"tp":30,"fp":5,"fn":5,"tn":60,"precision":0.8571428571428571,"recall":0.8571428571428571,"f1":0.8571428571428571,"matrix":{"contradiction:contradiction":30,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":5,"update:contradiction":3,"update:update":9,"update:compatible":0,"update:unrelated":3,"compatible:contradiction":2,"compatible:update":0,"compatible:compatible":11,"compatible:unrelated":12,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #legal filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #pricing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo scopes: general containers at EUR 5,000 versus refrigerated containers at EUR 50,000.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is a correction of a general pallet price while the other sets a price specifically for refrigerated pallets, so they concern different subjects.","note":"author corrects the signed pallet price"},{"id":"v042","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Engineering cancelled the December slot for NovaPay offline mode while product still commits it to the December release for Tundra Retail.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.","note":"author corrects the surcharge currency"},{"id":"v048","label":"update","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for each Cobalt Freight integration, so they can coexist.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"residency plus an encryption requirement"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T19:53:49+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":404.843,"llm_calls":155,"mean_latency_s":2.2561,"usage_reported":true,"prompt_tokens":250786,"completion_tokens":18258,"total_tokens":269044,"tp":30,"fp":6,"fn":5,"tn":59,"precision":0.8333333333333334,"recall":0.8571428571428571,"f1":0.8450704225352113,"matrix":{"contradiction:contradiction":30,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":5,"update:contradiction":3,"update:update":9,"update:compatible":0,"update:unrelated":3,"compatible:contradiction":3,"compatible:update":0,"compatible:compatible":12,"compatible:unrelated":10,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #legal filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #pricing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo types, general containers versus refrigerated containers, so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is a general pallet price correction while the other concerns specifically refrigerated pallets, so they are different subjects.","note":"author corrects the signed pallet price"},{"id":"v042","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Engineering cancelled the December slot for NovaPay offline mode while product still commits it to the December release for Tundra Retail.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, 250 EUR versus 250 USD.","note":"author corrects the surcharge currency"},{"id":"v048","label":"update","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.86,"reason":"Both claims set the Cobalt Freight integration's hourly rate limit but give mutually exclusive values, 1200 vs 600 requests per hour.","note":"approved exception doubles one integration limit"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing says agencies get a 30-day post-quarter waiver before the Solstice Travel fee applies, while pricing says the fee takes effect at end of quarter for all agencies.","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"residency plus an encryption requirement"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T20:00:35+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":323.5,"llm_calls":154,"mean_latency_s":1.7445,"usage_reported":true,"prompt_tokens":248862,"completion_tokens":18239,"total_tokens":267101,"tp":30,"fp":5,"fn":5,"tn":60,"precision":0.8571428571428571,"recall":0.8571428571428571,"f1":0.8571428571428571,"matrix":{"contradiction:contradiction":30,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":5,"update:contradiction":3,"update:update":9,"update:compatible":0,"update:unrelated":3,"compatible:contradiction":2,"compatible:update":0,"compatible:compatible":12,"compatible:unrelated":11,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #legal filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #pricing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo scopes: general containers at EUR 5,000 versus refrigerated containers at EUR 50,000.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.","note":"author corrects the signed pallet price"},{"id":"v042","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Engineering cancelled the December slot for NovaPay offline mode while product still commits it to the December release for Tundra Retail.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, 250 EUR versus 250 USD.","note":"author corrects the surcharge currency"},{"id":"v048","label":"update","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.78,"reason":"Both state a specific hourly rate limit for the same Cobalt Freight integration, 1200 vs 600, which cannot both be the effective limit.","note":"approved exception doubles one integration limit"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"residency plus an encryption requirement"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-07T00:06:53+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":267.094,"llm_calls":165,"mean_latency_s":1.261,"usage_reported":true,"prompt_tokens":269919,"completion_tokens":18730,"total_tokens":288649,"tp":30,"fp":5,"fn":5,"tn":60,"precision":0.8571428571428571,"recall":0.8571428571428571,"f1":0.8571428571428571,"matrix":{"contradiction:contradiction":30,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":5,"update:contradiction":3,"update:update":10,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":2,"compatible:update":0,"compatible:compatible":16,"compatible:unrelated":7,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #legal filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #pricing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The two limits apply to different cargo scopes \u2014 general containers vs refrigerated containers \u2014 so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Platform says siloTemp retention was reduced to 6 months globally today, while research asserts 18 months for grain customers, and both are active now.","note":"retention policy replaces the old figure"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is a global scope while the December commitment is specific to Tundra Retail, so they concern different scopes.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both claims set the same Maremar surcharge starting in March but in different currencies, EUR versus USD, which cannot both be the same amount.","note":"author corrects the surcharge currency"},{"id":"v049","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.","note":"compliance narrows the residency addendum"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The Thursday schedule is an approved exception for the Valpara\u00edso clinic, a narrower scope than the general Tuesday policy for all Vela Health clinics.","note":"authorized delivery day exception for one clinic"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is about general data retention policy with a maintenance exclusion, the other about siloTemp sensor reading retention, which are different subjects.","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.","note":"approved exception doubles one integration limit"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The 200-kit limit applies to Harborview Clinic generally while the 400-kit exception is scoped specifically to Harborview Clinic downtown, a different scope.","note":"signed exception doubles kit storage for one site"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"One claim sets a coverage limit while the other excludes a specific peril, so they address different subjects and can both hold.","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-07T00:11:35+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":252.828,"llm_calls":165,"mean_latency_s":1.1754,"usage_reported":true,"prompt_tokens":269929,"completion_tokens":18747,"total_tokens":288676,"tp":30,"fp":6,"fn":5,"tn":59,"precision":0.8333333333333334,"recall":0.8571428571428571,"f1":0.8450704225352113,"matrix":{"contradiction:contradiction":30,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":5,"update:contradiction":4,"update:update":10,"update:compatible":0,"update:unrelated":1,"compatible:contradiction":2,"compatible:update":0,"compatible:compatible":16,"compatible:unrelated":7,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #legal filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #pricing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The two limits apply to different cargo scopes \u2014 general containers vs refrigerated containers \u2014 so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Platform says siloTemp retention was cut to 6 months globally today, while research asserts 18-month retention for grain customers, which cannot both hold now.","note":"retention policy replaces the old figure"},{"id":"v042","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Engineering cancelled the December slot for NovaPay offline mode while product committed it to the December release for Tundra Retail.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both claims set the same Maremar surcharge starting in March but in different currencies, EUR versus USD, which cannot both be the same amount.","note":"author corrects the surcharge currency"},{"id":"v049","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.","note":"compliance narrows the residency addendum"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The Thursday schedule is an approved exception for the Valpara\u00edso clinic, a narrower scope than the general Tuesday policy for all Vela Health clinics.","note":"authorized delivery day exception for one clinic"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is about general data retention policy with a maintenance exclusion, the other about siloTemp sensor reading retention, which are different subjects.","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.","note":"approved exception doubles one integration limit"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The 200-kit limit applies to Harborview Clinic generally while the 400-kit exception is a signed exception for the specific Harborview Clinic downtown site.","note":"signed exception doubles kit storage for one site"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"One claim sets a coverage limit while the other excludes a specific peril, so they address different subjects and can both hold.","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-07T00:16:00+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":266.657,"llm_calls":165,"mean_latency_s":1.2438,"usage_reported":true,"prompt_tokens":269916,"completion_tokens":18728,"total_tokens":288644,"tp":30,"fp":5,"fn":5,"tn":60,"precision":0.8571428571428571,"recall":0.8571428571428571,"f1":0.8571428571428571,"matrix":{"contradiction:contradiction":30,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":5,"update:contradiction":3,"update:update":10,"update:compatible":0,"update:unrelated":2,"compatible:contradiction":2,"compatible:update":0,"compatible:compatible":16,"compatible:unrelated":7,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #legal filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #pricing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo scopes: general containers at EUR 5,000 versus refrigerated containers at EUR 50,000.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they are different subjects.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Platform says siloTemp retention was cut to 6 months globally today, while research asserts 18-month retention for grain customers, which cannot both hold now.","note":"retention policy replaces the old figure"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is a global scope while the December commitment is specific to Tundra Retail, so they concern different scopes.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both claims set the same Maremar surcharge starting in March but in different currencies, EUR versus USD, which cannot both be the same amount.","note":"author corrects the surcharge currency"},{"id":"v049","label":"update","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"One claim says all Meridian Bank data stays in Zurich while the other limits Zurich residency to payment data only, which cannot both be true.","note":"compliance narrows the residency addendum"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.9,"reason":"The Thursday schedule is an approved exception for the Valpara\u00edso clinic, a narrower scope than the general Tuesday policy for all Vela Health clinics.","note":"authorized delivery day exception for one clinic"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is about general data retention policy with a maintenance exclusion, the other about siloTemp sensor reading retention, which are different subjects.","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.","note":"approved exception doubles one integration limit"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing says agencies get a 30-day waiver after quarter end before the fee applies, while pricing says the fee takes effect at quarter end for all agencies.","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The 200-kit limit applies to Harborview Clinic generally while the 400-kit exception is scoped specifically to Harborview Clinic downtown, a different scope.","note":"signed exception doubles kit storage for one site"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"One claim sets a coverage limit while the other excludes a specific peril, so they address different subjects and can both hold.","note":"coverage plus an explicit exclusion"}]}] -->
