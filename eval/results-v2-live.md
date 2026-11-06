# Splitbrain — live brain evaluation

- Latest run (UTC): 2026-11-06T08:10:26+00:00
- LLM mode: `live`
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Dataset: `eval/dataset-v2.jsonl` — 100 pairs (contradiction=35, update=15, compatible=25, unrelated=25)
- Language mix: en=70, es=18, mixed=12
- Runs recorded: 3
- Pipeline: prefilter -> extraction -> matching -> classification -> candidate (threshold 0.7), identical to the Sentinel.
- Token usage across 3 run(s): input=485450, output=35684, total=521134 (mean per run: 161817 in / 11895 out / 173711 total; API dollar costs are not estimated).

## Summary across live runs

| run | UTC | precision | recall | F1 | TP / FP / FN / TN | errors | LLM calls | total time | mean latency / call | tokens (in / out / total) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-06T07:59:57+00:00 | 0.913 | 0.600 | 0.724 | 21 / 2 / 14 / 63 | 42 | 100 | 287.94s | 2.525s | 161815 / 11892 / 173707 |
| 2 | 2026-11-06T08:04:47+00:00 | 0.955 | 0.600 | 0.737 | 21 / 1 / 14 / 64 | 42 | 100 | 336.36s | 3.009s | 161814 / 11896 / 173710 |
| 3 | 2026-11-06T08:10:26+00:00 | 0.913 | 0.600 | 0.724 | 21 / 2 / 14 / 63 | 43 | 100 | 363.69s | 3.257s | 161821 / 11896 / 173717 |
| **Mean** | — | **0.927** | **0.600** | **0.728** | 21.0 / 1.7 / 14.0 / 63.3 | 42.3 | 100.0 | 329.33s | 2.930s | 161817 / 11895 / 173711 |

## Run 1 — 2026-11-06T07:59:57+00:00

- Run (UTC): 2026-11-06T07:59:57+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 287.94s
- LLM calls: 100 (mean latency 2.525s per call)
- Token usage: input=161815, output=11892, total=173707 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.913 |
| recall | 0.600 |
| F1 | 0.724 |
| TP / FP / FN / TN | 21 / 2 / 14 / 63 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 21 | 0 | 0 | 14 |
| update | 1 | 5 | 0 | 9 |
| compatible | 1 | 0 | 7 | 17 |
| unrelated | 0 | 0 | 0 | 25 |

### Errors (42)

#### v002 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg versus 500 lb on the same scanner limit
- A (#warehouse, elena): The PalletScan limit is 500 kg per pallet for all warehouses.
- B (#qa, ivan): Engineering set PalletScan to reject anything over 500 lb per pallet everywhere.

#### v003 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: end-of-quarter GA versus a Q3 slip
- A (#product, yara): FleetLink general availability is locked for the end of quarter for every fleet customer.
- B (#fleet, mateo): FleetLink general availability slipped to Q3, we are not shipping at the end of quarter.

#### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

#### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #quality filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

#### v010 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: 300 seats versus 30 seats in two languages
- A (#campus, sira): Piedmont University bought 300 DeskPass seats for the spring term, that is in the order form.
- B (#ventas, teo): El pedido de Piedmont University es de 30 asientos de DeskPass para el semestre de primavera.

#### v013 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: 98% versus 90% solar inverter availability
- A (#operaciones, yara): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, mateo): Operaciones solo puede garantizar un 90% de disponibilidad en los inversores solares de Nordvik Energi.

#### v017 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: drone restocking approved versus banned
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): Safety banned drone restocking at every Tundra Retail distribution centre until further notice.

#### v019 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: 20 kg versus 20 lb luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Operations set the Solstice Travel luggage allowance to 20 lb per passenger on every ferry route.

#### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

#### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #billing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

#### v023 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #energia filtered out: no commitment signal (pure chatter)
- Note: 8 hours versus 8 minutes of battery backup
- A (#energy, yara): Nordvik Energi microgrid batteries are rated for 8 hours of backup from day one.
- B (#energia, mateo): Las baterías de Nordvik Energi solo cubren 8 minutos de respaldo según la ficha técnica.

#### v025 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #operaciones filtered out: no commitment signal (pure chatter)
- Note: before end of quarter versus not until next year
- A (#ventas, ines): Confirmamos a Orchid Hotels que SmartLocker estará instalado antes de fin de trimestre.
- B (#operaciones, bruno): Instalaciones avisó que SmartLocker para Orchid Hotels no se instalará hasta el próximo año.

#### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo types — general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 — so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

#### v035 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #sistemas filtered out: no commitment signal (pure chatter)
- Note: 500 pages versus 50 pages printing quota
- A (#campus, ines): Piedmont University raised printing quotas to 500 pages per student each term.
- B (#sistemas, bruno): Piedmont University printing quotas are set to 50 pages per student each term.

#### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject scope.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

#### v039 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #research filtered out: no commitment signal (pure chatter)
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

#### v040 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #support filtered out: no commitment signal (pure chatter)
- Note: author corrects their own SLA number
- A (#partners, clara): Orchid Hotels SmartLocker incidents carry a four-hour response SLA from Monday.
- B (#support, hugo): Correction to my own post: the Orchid Hotels response SLA is two hours, not four.

#### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

#### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both claims set the same Maremar surcharge from March but in different currencies, EUR versus USD, which cannot both be the same amount.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

#### v046 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: signed order supersedes the quoted seat count
- A (#campus, ines): Piedmont University bought 300 DeskPass seats for the spring term.
- B (#billing, bruno): Update from sales ops: the signed Piedmont University order is 350 DeskPass seats, superseding 300.

#### v047 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #almacen filtered out: no commitment signal (pure chatter)
- Note: operations widens the pilot to five warehouses
- A (#almacen, yara): El piloto de drone restocking con Boreal Foods arranca en tres almacenes.
- B (#operaciones, mateo): Aviso de operaciones: el piloto de Boreal Foods arranca en cinco almacenes, deja sin efecto los tres.

#### v048 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

#### v049 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

#### v050 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

#### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

#### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

#### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

#### v056 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #engineering filtered out: no commitment signal (pure chatter)
- Note: release feature plus an extra queue detail
- A (#product, lena): NovaPay offline mode is included in the January release for Tundra Retail terminals.
- B (#engineering, pavel): NovaPay offline mode also supports a 72-hour transaction queue for Tundra Retail terminals.

#### v057 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #fleet filtered out: no commitment signal (pure chatter)
- Note: pilot scope then wider rollout
- A (#fleet, aisha): The GreenRoute pilot with Ferrovia Rail covers two routes until fin de trimestre.
- B (#producto, diego): GreenRoute se amplía a todas las rutas de Ferrovia Rail en Q3, tras finalizar el piloto.

#### v058 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

#### v060 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.86
- Reason: Both claims set the Cobalt Freight integration's hourly rate limit but give mutually exclusive values, 1200 vs 600 requests per hour.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

#### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

#### v062 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: base seats plus an optional extension
- A (#campus, ines): Piedmont University compró 300 asientos de DeskPass para el semestre de primavera.
- B (#ventas, bruno): Piedmont University puede ampliar DeskPass con 50 asientos adicionales bajo pedido desde abril.

#### v063 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

#### v065 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #pricing filtered out: no commitment signal (pure chatter)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

#### v067 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

#### v068 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

#### v069 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #producto filtered out: no commitment signal (pure chatter)
- Note: beta next Friday and GA at end of quarter
- A (#almacen, rosa): La beta de PalletScan para Casa Verde abre el próximo viernes en un almacén.
- B (#producto, omar): PalletScan llega a disponibilidad general para Casa Verde a fin de trimestre, después de la beta.

#### v071 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg written as 0.5 tonnes
- A (#warehouse, elena): PalletScan rejects pallets over 500 kg in every warehouse.
- B (#qa, ivan): The PalletScan threshold is written as 0.5 tonnes per pallet in the configuration guide.

#### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

#### v073 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

#### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

## Run 2 — 2026-11-06T08:04:47+00:00

- Run (UTC): 2026-11-06T08:04:47+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 336.36s
- LLM calls: 100 (mean latency 3.009s per call)
- Token usage: input=161814, output=11896, total=173710 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.955 |
| recall | 0.600 |
| F1 | 0.737 |
| TP / FP / FN / TN | 21 / 1 / 14 / 64 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 21 | 0 | 0 | 14 |
| update | 1 | 5 | 0 | 9 |
| compatible | 0 | 0 | 7 | 18 |
| unrelated | 0 | 0 | 0 | 25 |

### Errors (42)

#### v002 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg versus 500 lb on the same scanner limit
- A (#warehouse, elena): The PalletScan limit is 500 kg per pallet for all warehouses.
- B (#qa, ivan): Engineering set PalletScan to reject anything over 500 lb per pallet everywhere.

#### v003 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: end-of-quarter GA versus a Q3 slip
- A (#product, yara): FleetLink general availability is locked for the end of quarter for every fleet customer.
- B (#fleet, mateo): FleetLink general availability slipped to Q3, we are not shipping at the end of quarter.

#### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

#### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #quality filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

#### v010 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: 300 seats versus 30 seats in two languages
- A (#campus, sira): Piedmont University bought 300 DeskPass seats for the spring term, that is in the order form.
- B (#ventas, teo): El pedido de Piedmont University es de 30 asientos de DeskPass para el semestre de primavera.

#### v013 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: 98% versus 90% solar inverter availability
- A (#operaciones, yara): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, mateo): Operaciones solo puede garantizar un 90% de disponibilidad en los inversores solares de Nordvik Energi.

#### v017 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: drone restocking approved versus banned
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): Safety banned drone restocking at every Tundra Retail distribution centre until further notice.

#### v019 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: 20 kg versus 20 lb luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Operations set the Solstice Travel luggage allowance to 20 lb per passenger on every ferry route.

#### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

#### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #billing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

#### v023 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #energia filtered out: no commitment signal (pure chatter)
- Note: 8 hours versus 8 minutes of battery backup
- A (#energy, yara): Nordvik Energi microgrid batteries are rated for 8 hours of backup from day one.
- B (#energia, mateo): Las baterías de Nordvik Energi solo cubren 8 minutos de respaldo según la ficha técnica.

#### v025 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #operaciones filtered out: no commitment signal (pure chatter)
- Note: before end of quarter versus not until next year
- A (#ventas, ines): Confirmamos a Orchid Hotels que SmartLocker estará instalado antes de fin de trimestre.
- B (#operaciones, bruno): Instalaciones avisó que SmartLocker para Orchid Hotels no se instalará hasta el próximo año.

#### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The two limits apply to different cargo types — general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 — so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

#### v035 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #sistemas filtered out: no commitment signal (pure chatter)
- Note: 500 pages versus 50 pages printing quota
- A (#campus, ines): Piedmont University raised printing quotas to 500 pages per student each term.
- B (#sistemas, bruno): Piedmont University printing quotas are set to 50 pages per student each term.

#### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they address different subjects.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

#### v039 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #research filtered out: no commitment signal (pure chatter)
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

#### v040 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #support filtered out: no commitment signal (pure chatter)
- Note: author corrects their own SLA number
- A (#partners, clara): Orchid Hotels SmartLocker incidents carry a four-hour response SLA from Monday.
- B (#support, hugo): Correction to my own post: the Orchid Hotels response SLA is two hours, not four.

#### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is a general scope while the December commitment is specific to Tundra Retail, so the scopes differ.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

#### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

#### v046 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: signed order supersedes the quoted seat count
- A (#campus, ines): Piedmont University bought 300 DeskPass seats for the spring term.
- B (#billing, bruno): Update from sales ops: the signed Piedmont University order is 350 DeskPass seats, superseding 300.

#### v047 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #almacen filtered out: no commitment signal (pure chatter)
- Note: operations widens the pilot to five warehouses
- A (#almacen, yara): El piloto de drone restocking con Boreal Foods arranca en tres almacenes.
- B (#operaciones, mateo): Aviso de operaciones: el piloto de Boreal Foods arranca en cinco almacenes, deja sin efecto los tres.

#### v048 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

#### v049 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

#### v050 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

#### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

#### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

#### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

#### v056 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #engineering filtered out: no commitment signal (pure chatter)
- Note: release feature plus an extra queue detail
- A (#product, lena): NovaPay offline mode is included in the January release for Tundra Retail terminals.
- B (#engineering, pavel): NovaPay offline mode also supports a 72-hour transaction queue for Tundra Retail terminals.

#### v057 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #fleet filtered out: no commitment signal (pure chatter)
- Note: pilot scope then wider rollout
- A (#fleet, aisha): The GreenRoute pilot with Ferrovia Rail covers two routes until fin de trimestre.
- B (#producto, diego): GreenRoute se amplía a todas las rutas de Ferrovia Rail en Q3, tras finalizar el piloto.

#### v058 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

#### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: The 1200/hour figure is an approved exception for the holiday integration, while 600/hour is the standard customs broker API policy, so both can hold.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

#### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

#### v062 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: base seats plus an optional extension
- A (#campus, ines): Piedmont University compró 300 asientos de DeskPass para el semestre de primavera.
- B (#ventas, bruno): Piedmont University puede ampliar DeskPass con 50 asientos adicionales bajo pedido desde abril.

#### v063 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

#### v065 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #pricing filtered out: no commitment signal (pure chatter)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

#### v067 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

#### v068 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

#### v069 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #producto filtered out: no commitment signal (pure chatter)
- Note: beta next Friday and GA at end of quarter
- A (#almacen, rosa): La beta de PalletScan para Casa Verde abre el próximo viernes en un almacén.
- B (#producto, omar): PalletScan llega a disponibilidad general para Casa Verde a fin de trimestre, después de la beta.

#### v071 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg written as 0.5 tonnes
- A (#warehouse, elena): PalletScan rejects pallets over 500 kg in every warehouse.
- B (#qa, ivan): The PalletScan threshold is written as 0.5 tonnes per pallet in the configuration guide.

#### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

#### v073 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

#### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

## Run 3 — 2026-11-06T08:10:26+00:00

- Run (UTC): 2026-11-06T08:10:26+00:00
- Model: `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- Endpoint (Base URL): `https://api.river.ai/v1`
- Total run time: 363.69s
- LLM calls: 100 (mean latency 3.257s per call)
- Token usage: input=161821, output=11896, total=173717 (costs are not estimated)

### Metrics for `contradiction`

| metric | value |
| --- | --- |
| precision | 0.913 |
| recall | 0.600 |
| F1 | 0.724 |
| TP / FP / FN / TN | 21 / 2 / 14 / 63 |

### Confusion matrix

| label \ predicted | contradiction | update | compatible | unrelated |
| --- | --- | --- | --- | --- |
| contradiction | 21 | 0 | 0 | 14 |
| update | 1 | 5 | 0 | 9 |
| compatible | 1 | 0 | 6 | 18 |
| unrelated | 0 | 0 | 0 | 25 |

### Errors (43)

#### v002 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg versus 500 lb on the same scanner limit
- A (#warehouse, elena): The PalletScan limit is 500 kg per pallet for all warehouses.
- B (#qa, ivan): Engineering set PalletScan to reject anything over 500 lb per pallet everywhere.

#### v003 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: end-of-quarter GA versus a Q3 slip
- A (#product, yara): FleetLink general availability is locked for the end of quarter for every fleet customer.
- B (#fleet, mateo): FleetLink general availability slipped to Q3, we are not shipping at the end of quarter.

#### v007 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: Zurich residency versus a Toronto migration
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#platform, felix): We are migrating Meridian Bank data to the Toronto region this quarter for all workloads.

#### v008 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #quality filtered out: no commitment signal (pure chatter)
- Note: excursion credits promised then removed
- A (#quality, rosa): Casa Verde receives a full credit for every temperature excursion above two degrees.
- B (#legal, omar): Legal removed all temperature excursion credits from the Casa Verde contract this week.

#### v010 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: 300 seats versus 30 seats in two languages
- A (#campus, sira): Piedmont University bought 300 DeskPass seats for the spring term, that is in the order form.
- B (#ventas, teo): El pedido de Piedmont University es de 30 asientos de DeskPass para el semestre de primavera.

#### v013 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: 98% versus 90% solar inverter availability
- A (#operaciones, yara): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, mateo): Operaciones solo puede garantizar un 90% de disponibilidad en los inversores solares de Nordvik Energi.

#### v017 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: drone restocking approved versus banned
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): Safety banned drone restocking at every Tundra Retail distribution centre until further notice.

#### v019 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: 20 kg versus 20 lb luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Operations set the Solstice Travel luggage allowance to 20 lb per passenger on every ferry route.

#### v020 — label `contradiction`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: 18 months of readings versus deletion after 30 days
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): We are deleting siloTemp sensor readings after 30 days for every grain account.

#### v021 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #billing filtered out: no commitment signal (pure chatter)
- Note: signed fee exemption versus exemption removed
- A (#billing, nadia): Lumen Labs is the only customer exempt from the e-invoicing gateway fee, signed off by finance.
- B (#pricing, ravi): Finance removed the e-invoicing gateway exemption for Lumen Labs; they pay the standard fee now.

#### v023 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #energia filtered out: no commitment signal (pure chatter)
- Note: 8 hours versus 8 minutes of battery backup
- A (#energy, yara): Nordvik Energi microgrid batteries are rated for 8 hours of backup from day one.
- B (#energia, mateo): Las baterías de Nordvik Energi solo cubren 8 minutos de respaldo según la ficha técnica.

#### v025 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #operaciones filtered out: no commitment signal (pure chatter)
- Note: before end of quarter versus not until next year
- A (#ventas, ines): Confirmamos a Orchid Hotels que SmartLocker estará instalado antes de fin de trimestre.
- B (#operaciones, bruno): Instalaciones avisó que SmartLocker para Orchid Hotels no se instalará hasta el próximo año.

#### v032 — label `contradiction`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: The 50,000 EUR limit applies specifically to refrigerated containers, a narrower scope than the general 5,000 EUR per-container limit, so both can hold.
- Note: 50.000 EUR versus 5.000 EUR container coverage
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#finanzas, ivan): La póliza de Atlas Insurance limita la cobertura a 5.000 EUR por contenedor desde enero.

#### v035 — label `contradiction`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #sistemas filtered out: no commitment signal (pure chatter)
- Note: 500 pages versus 50 pages printing quota
- A (#campus, ines): Piedmont University raised printing quotas to 500 pages per student each term.
- B (#sistemas, bruno): Piedmont University printing quotas are set to 50 pages per student each term.

#### v036 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject.
- Note: author corrects the signed pallet price
- A (#pricing, ravi): Kestrel Logistics will pay 40 USD per refrigerated pallet from next Friday.
- B (#billing, nadia): Correction to my earlier note: Kestrel Logistics signed at 45 USD per pallet, not 40.

#### v039 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #research filtered out: no commitment signal (pure chatter)
- Note: retention policy replaces the old figure
- A (#research, sira): Las lecturas de siloTemp se conservan 18 meses para todos los clientes de grano.
- B (#platform, teo): Update: siloTemp retention was reduced to 6 months today; the 18-month note is void.

#### v040 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #support filtered out: no commitment signal (pure chatter)
- Note: author corrects their own SLA number
- A (#partners, clara): Orchid Hotels SmartLocker incidents carry a four-hour response SLA from Monday.
- B (#support, hugo): Correction to my own post: the Orchid Hotels response SLA is two hours, not four.

#### v042 — label `update`, predicted `unrelated`

- Stage: `classification`, confidence=0.88
- Reason: Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.
- Note: engineering moves the offline mode release
- A (#product, lena): NovaPay offline mode ships with the December release for Tundra Retail.
- B (#engineering, pavel): Engineering update: NovaPay offline mode now ships in January, the December slot is cancelled.

#### v044 — label `update`, predicted `contradiction`

- Stage: `classification`, confidence=0.90
- Reason: Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.
- Note: author corrects the surcharge currency
- A (#finanzas, rosa): Maremar refrigerated container surcharge is 250 USD starting in March.
- B (#billing, omar): Correction to my earlier note: the Maremar surcharge is 250 EUR starting in March.

#### v046 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: signed order supersedes the quoted seat count
- A (#campus, ines): Piedmont University bought 300 DeskPass seats for the spring term.
- B (#billing, bruno): Update from sales ops: the signed Piedmont University order is 350 DeskPass seats, superseding 300.

#### v047 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #almacen filtered out: no commitment signal (pure chatter)
- Note: operations widens the pilot to five warehouses
- A (#almacen, yara): El piloto de drone restocking con Boreal Foods arranca en tres almacenes.
- B (#operaciones, mateo): Aviso de operaciones: el piloto de Boreal Foods arranca en cinco almacenes, deja sin efecto los tres.

#### v048 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #travel filtered out: no commitment signal (pure chatter)
- Note: author corrects the luggage allowance
- A (#travel, lena): Solstice Travel luggage allowance is 20 kg per passenger on every ferry route.
- B (#ops, pavel): Correction: Solstice Travel allowance is 25 kg per passenger, the 20 kg note was wrong.

#### v049 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: compliance narrows the residency addendum
- A (#compliance, noa): Meridian Bank addendum keeps all data in the Zurich region going forward.
- B (#legal, felix): Actualización de cumplimiento: el addendum de Meridian Bank exige Zúrich solo para datos de pagos.

#### v050 — label `update`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #operaciones filtered out: no commitment signal (pure chatter)
- Note: author corrects the availability commitment
- A (#operaciones, elena): Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los inversores solares.
- B (#energia, ivan): Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%.

#### v051 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: March beta and Q2 GA are two phases
- A (#clinic-ops, clara): SampleTrack beta opens for Harborview Clinic on March 3 in two labs.
- B (#product, hugo): SampleTrack general availability follows in Q2 after the March beta for Harborview Clinic.

#### v052 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: signed exception for one site of the same customer
- A (#pricing, nadia): Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.
- B (#billing, ravi): Finance approved a signed exception: the Kestrel Logistics Oslo site pays 32 USD per pallet.

#### v055 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different scope)
- Note: authorized delivery day exception for one clinic
- A (#clinic-ops, diego): Todas las clínicas de Vela Health reciben muestras de laboratorio los martes desde febrero.
- B (#direccion, ines): Dirección autorizó una excepción: la clínica de Vela Health en Valparaíso recibe muestras los jueves.

#### v056 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #engineering filtered out: no commitment signal (pure chatter)
- Note: release feature plus an extra queue detail
- A (#product, lena): NovaPay offline mode is included in the January release for Tundra Retail terminals.
- B (#engineering, pavel): NovaPay offline mode also supports a 72-hour transaction queue for Tundra Retail terminals.

#### v057 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #fleet filtered out: no commitment signal (pure chatter)
- Note: pilot scope then wider rollout
- A (#fleet, aisha): The GreenRoute pilot with Ferrovia Rail covers two routes until fin de trimestre.
- B (#producto, diego): GreenRoute se amplía a todas las rutas de Ferrovia Rail en Q3, tras finalizar el piloto.

#### v058 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #platform filtered out: no commitment signal (pure chatter)
- Note: retention plus a maintenance carve-out
- A (#research, sira): siloTemp sensor readings are retained for 18 months for all grain customers.
- B (#platform, teo): The 18-month retention excludes a weekly 30-minute maintenance window for all grain customers.

#### v060 — label `compatible`, predicted `unrelated`

- Stage: `classification`, confidence=0.80
- Reason: One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.
- Note: approved exception doubles one integration limit
- A (#product, clara): The customs broker API allows 600 requests per hour for each Cobalt Freight integration.
- B (#platform, hugo): An approved exception gives the Cobalt Freight holiday integration 1200 requests per hour.

#### v061 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: December beta and Q2 GA for one logistics customer
- A (#product, yara): FleetLink beta opens for Kestrel Logistics on December 1 with 20 vans.
- B (#fleet, mateo): FleetLink general availability for Kestrel Logistics is planned for Q2 after the December beta.

#### v062 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #campus filtered out: no commitment signal (pure chatter)
- Note: base seats plus an optional extension
- A (#campus, ines): Piedmont University compró 300 asientos de DeskPass para el semestre de primavera.
- B (#ventas, bruno): Piedmont University puede ampliar DeskPass con 50 asientos adicionales bajo pedido desde abril.

#### v063 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: approval with one explicitly excluded centre
- A (#warehouse, noa): Drone restocking is approved for all Tundra Retail distribution centres from Monday.
- B (#compliance, felix): The approval excludes the Tundra Retail rooftop centre, which stays manual until the safety review.

#### v065 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #pricing filtered out: no commitment signal (pure chatter)
- Note: fee at end of quarter plus a 30-day waiver
- A (#pricing, aisha): The Solstice Travel booking fee takes effect at the end of quarter for all agencies.
- B (#billing, diego): Agencies get a 30-day waiver after the end of quarter before the Solstice Travel fee applies.

#### v067 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #compliance filtered out: no commitment signal (pure chatter)
- Note: signed exception doubles kit storage for one site
- A (#clinic-ops, clara): Every Harborview Clinic can store 200 clinical trial kits on site from January.
- B (#compliance, hugo): Compliance granted Harborview Clinic downtown a signed exception for 400 kits on site.

#### v068 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #compliance filtered out: no commitment signal (pure chatter)
- Note: residency plus an encryption requirement
- A (#compliance, noa): Meridian Bank data must remain in the Zurich region under the signed addendum.
- B (#seguridad, felix): El addendum de Meridian Bank también exige cifrado en reposo para la región de Zúrich.

#### v069 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message b in #producto filtered out: no commitment signal (pure chatter)
- Note: beta next Friday and GA at end of quarter
- A (#almacen, rosa): La beta de PalletScan para Casa Verde abre el próximo viernes en un almacén.
- B (#producto, omar): PalletScan llega a disponibilidad general para Casa Verde a fin de trimestre, después de la beta.

#### v070 — label `compatible`, predicted `contradiction`

- Stage: `classification`, confidence=0.88
- Reason: Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.
- Note: signed exception for marketplace invoices
- A (#billing, ines): Quanta Retail invoices are payable within 45 days under the renewed agreement.
- B (#legal, bruno): Finance signed an exception: Quanta Retail marketplace invoices are payable within 60 days.

#### v071 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #warehouse filtered out: no commitment signal (pure chatter)
- Note: 500 kg written as 0.5 tonnes
- A (#warehouse, elena): PalletScan rejects pallets over 500 kg in every warehouse.
- B (#qa, ivan): The PalletScan threshold is written as 0.5 tonnes per pallet in the configuration guide.

#### v072 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: shuttle hours plus an extra Friday route
- A (#campus, sira): The Piedmont University campus shuttle runs until 22:00 starting Monday.
- B (#transport, teo): Piedmont University also adds a Friday night campus shuttle route from April.

#### v073 — label `compatible`, predicted `unrelated`

- Stage: `prefilter`
- Reason: message a in #product filtered out: no commitment signal (pure chatter)
- Note: guided pilot before the end-of-quarter launch
- A (#product, yara): Aurora assistant general availability is locked for the end of quarter for Sierra Telecom.
- B (#support, mateo): Sierra Telecom agents join a guided pilot next Friday before the end-of-quarter launch.

#### v074 — label `compatible`, predicted `unrelated`

- Stage: `matching`
- Reason: matcher rejected the pair (different subject)
- Note: coverage plus an explicit exclusion
- A (#legal, elena): Atlas Insurance cubre hasta 50.000 EUR por contenedor de carga refrigerada desde enero.
- B (#riesgos, ivan): La póliza de Atlas Insurance excluye daños por corte de energía de esa cobertura desde enero.

<!-- splitbrain-live-runs [{"run_utc":"2026-11-06T07:59:57+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":287.937,"llm_calls":100,"mean_latency_s":2.5253,"usage_reported":true,"prompt_tokens":161815,"completion_tokens":11892,"total_tokens":173707,"tp":21,"fp":2,"fn":14,"tn":63,"precision":0.9130434782608695,"recall":0.6,"f1":0.7241379310344828,"matrix":{"contradiction:contradiction":21,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":14,"update:contradiction":1,"update:update":5,"update:compatible":0,"update:unrelated":9,"compatible:contradiction":1,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":17,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v002","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg versus 500 lb on the same scanner limit"},{"id":"v003","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"end-of-quarter GA versus a Q3 slip"},{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #quality filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v010","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"300 seats versus 30 seats in two languages"},{"id":"v013","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"98% versus 90% solar inverter availability"},{"id":"v017","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"drone restocking approved versus banned"},{"id":"v019","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"20 kg versus 20 lb luggage allowance"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #billing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v023","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #energia filtered out: no commitment signal (pure chatter)","note":"8 hours versus 8 minutes of battery backup"},{"id":"v025","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #operaciones filtered out: no commitment signal (pure chatter)","note":"before end of quarter versus not until next year"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo types \u2014 general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 \u2014 so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v035","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #sistemas filtered out: no commitment signal (pure chatter)","note":"500 pages versus 50 pages printing quota"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject scope.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #research filtered out: no commitment signal (pure chatter)","note":"retention policy replaces the old figure"},{"id":"v040","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #support filtered out: no commitment signal (pure chatter)","note":"author corrects their own SLA number"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both claims set the same Maremar surcharge from March but in different currencies, EUR versus USD, which cannot both be the same amount.","note":"author corrects the surcharge currency"},{"id":"v046","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"signed order supersedes the quoted seat count"},{"id":"v047","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #almacen filtered out: no commitment signal (pure chatter)","note":"operations widens the pilot to five warehouses"},{"id":"v048","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v056","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #engineering filtered out: no commitment signal (pure chatter)","note":"release feature plus an extra queue detail"},{"id":"v057","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #fleet filtered out: no commitment signal (pure chatter)","note":"pilot scope then wider rollout"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.86,"reason":"Both claims set the Cobalt Freight integration's hourly rate limit but give mutually exclusive values, 1200 vs 600 requests per hour.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v062","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"base seats plus an optional extension"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #pricing filtered out: no commitment signal (pure chatter)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"residency plus an encryption requirement"},{"id":"v069","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #producto filtered out: no commitment signal (pure chatter)","note":"beta next Friday and GA at end of quarter"},{"id":"v071","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg written as 0.5 tonnes"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T08:04:47+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":336.36,"llm_calls":100,"mean_latency_s":3.0085,"usage_reported":true,"prompt_tokens":161814,"completion_tokens":11896,"total_tokens":173710,"tp":21,"fp":1,"fn":14,"tn":64,"precision":0.9545454545454546,"recall":0.6,"f1":0.7368421052631579,"matrix":{"contradiction:contradiction":21,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":14,"update:contradiction":1,"update:update":5,"update:compatible":0,"update:unrelated":9,"compatible:contradiction":0,"compatible:update":0,"compatible:compatible":7,"compatible:unrelated":18,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v002","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg versus 500 lb on the same scanner limit"},{"id":"v003","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"end-of-quarter GA versus a Q3 slip"},{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #quality filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v010","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"300 seats versus 30 seats in two languages"},{"id":"v013","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"98% versus 90% solar inverter availability"},{"id":"v017","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"drone restocking approved versus banned"},{"id":"v019","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"20 kg versus 20 lb luggage allowance"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #billing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v023","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #energia filtered out: no commitment signal (pure chatter)","note":"8 hours versus 8 minutes of battery backup"},{"id":"v025","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #operaciones filtered out: no commitment signal (pure chatter)","note":"before end of quarter versus not until next year"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The two limits apply to different cargo types \u2014 general containers at EUR 5,000 versus refrigerated containers at EUR 50,000 \u2014 so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v035","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #sistemas filtered out: no commitment signal (pure chatter)","note":"500 pages versus 50 pages printing quota"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns a specifically refrigerated pallet price, so they address different subjects.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #research filtered out: no commitment signal (pure chatter)","note":"retention policy replaces the old figure"},{"id":"v040","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #support filtered out: no commitment signal (pure chatter)","note":"author corrects their own SLA number"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is a general scope while the December commitment is specific to Tundra Retail, so the scopes differ.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.","note":"author corrects the surcharge currency"},{"id":"v046","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"signed order supersedes the quoted seat count"},{"id":"v047","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #almacen filtered out: no commitment signal (pure chatter)","note":"operations widens the pilot to five warehouses"},{"id":"v048","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v056","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #engineering filtered out: no commitment signal (pure chatter)","note":"release feature plus an extra queue detail"},{"id":"v057","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #fleet filtered out: no commitment signal (pure chatter)","note":"pilot scope then wider rollout"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"The 1200/hour figure is an approved exception for the holiday integration, while 600/hour is the standard customs broker API policy, so both can hold.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v062","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"base seats plus an optional extension"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #pricing filtered out: no commitment signal (pure chatter)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"residency plus an encryption requirement"},{"id":"v069","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #producto filtered out: no commitment signal (pure chatter)","note":"beta next Friday and GA at end of quarter"},{"id":"v071","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg written as 0.5 tonnes"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]},{"run_utc":"2026-11-06T08:10:26+00:00","model":"deepseek-ai/DeepSeek-V4.1-Flash-1017","base_url":"https://api.river.ai/v1","duration_s":363.687,"llm_calls":100,"mean_latency_s":3.2567,"usage_reported":true,"prompt_tokens":161821,"completion_tokens":11896,"total_tokens":173717,"tp":21,"fp":2,"fn":14,"tn":63,"precision":0.9130434782608695,"recall":0.6,"f1":0.7241379310344828,"matrix":{"contradiction:contradiction":21,"contradiction:update":0,"contradiction:compatible":0,"contradiction:unrelated":14,"update:contradiction":1,"update:update":5,"update:compatible":0,"update:unrelated":9,"compatible:contradiction":1,"compatible:update":0,"compatible:compatible":6,"compatible:unrelated":18,"unrelated:contradiction":0,"unrelated:update":0,"unrelated:compatible":0,"unrelated:unrelated":25},"errors":[{"id":"v002","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg versus 500 lb on the same scanner limit"},{"id":"v003","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"end-of-quarter GA versus a Q3 slip"},{"id":"v007","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"Zurich residency versus a Toronto migration"},{"id":"v008","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #quality filtered out: no commitment signal (pure chatter)","note":"excursion credits promised then removed"},{"id":"v010","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"300 seats versus 30 seats in two languages"},{"id":"v013","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"98% versus 90% solar inverter availability"},{"id":"v017","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"drone restocking approved versus banned"},{"id":"v019","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"20 kg versus 20 lb luggage allowance"},{"id":"v020","label":"contradiction","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"18 months of readings versus deletion after 30 days"},{"id":"v021","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #billing filtered out: no commitment signal (pure chatter)","note":"signed fee exemption versus exemption removed"},{"id":"v023","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #energia filtered out: no commitment signal (pure chatter)","note":"8 hours versus 8 minutes of battery backup"},{"id":"v025","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #operaciones filtered out: no commitment signal (pure chatter)","note":"before end of quarter versus not until next year"},{"id":"v032","label":"contradiction","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"The 50,000 EUR limit applies specifically to refrigerated containers, a narrower scope than the general 5,000 EUR per-container limit, so both can hold.","note":"50.000 EUR versus 5.000 EUR container coverage"},{"id":"v035","label":"contradiction","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #sistemas filtered out: no commitment signal (pure chatter)","note":"500 pages versus 50 pages printing quota"},{"id":"v036","label":"update","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"Claim a is a correction of a general pallet price while claim b concerns specifically refrigerated pallets, a different subject.","note":"author corrects the signed pallet price"},{"id":"v039","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #research filtered out: no commitment signal (pure chatter)","note":"retention policy replaces the old figure"},{"id":"v040","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #support filtered out: no commitment signal (pure chatter)","note":"author corrects their own SLA number"},{"id":"v042","label":"update","predicted":"unrelated","stage":"classification","confidence":0.88,"reason":"Engineering's January decision is scoped to all customers while the December commitment is specific to Tundra Retail, so the scopes differ.","note":"engineering moves the offline mode release"},{"id":"v044","label":"update","predicted":"contradiction","stage":"classification","confidence":0.9,"reason":"Both state the Maremar refrigerated surcharge starting in March but in mutually exclusive currencies, EUR versus USD.","note":"author corrects the surcharge currency"},{"id":"v046","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"signed order supersedes the quoted seat count"},{"id":"v047","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #almacen filtered out: no commitment signal (pure chatter)","note":"operations widens the pilot to five warehouses"},{"id":"v048","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #travel filtered out: no commitment signal (pure chatter)","note":"author corrects the luggage allowance"},{"id":"v049","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"compliance narrows the residency addendum"},{"id":"v050","label":"update","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #operaciones filtered out: no commitment signal (pure chatter)","note":"author corrects the availability commitment"},{"id":"v051","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"March beta and Q2 GA are two phases"},{"id":"v052","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"signed exception for one site of the same customer"},{"id":"v055","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different scope)","note":"authorized delivery day exception for one clinic"},{"id":"v056","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #engineering filtered out: no commitment signal (pure chatter)","note":"release feature plus an extra queue detail"},{"id":"v057","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #fleet filtered out: no commitment signal (pure chatter)","note":"pilot scope then wider rollout"},{"id":"v058","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #platform filtered out: no commitment signal (pure chatter)","note":"retention plus a maintenance carve-out"},{"id":"v060","label":"compatible","predicted":"unrelated","stage":"classification","confidence":0.8,"reason":"One claim is an approved exception for the holiday integration at 1200 rph, the other a general 600 rph policy for the customs broker API, so they can coexist.","note":"approved exception doubles one integration limit"},{"id":"v061","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"December beta and Q2 GA for one logistics customer"},{"id":"v062","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #campus filtered out: no commitment signal (pure chatter)","note":"base seats plus an optional extension"},{"id":"v063","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"approval with one explicitly excluded centre"},{"id":"v065","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #pricing filtered out: no commitment signal (pure chatter)","note":"fee at end of quarter plus a 30-day waiver"},{"id":"v067","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #compliance filtered out: no commitment signal (pure chatter)","note":"signed exception doubles kit storage for one site"},{"id":"v068","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #compliance filtered out: no commitment signal (pure chatter)","note":"residency plus an encryption requirement"},{"id":"v069","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message b in #producto filtered out: no commitment signal (pure chatter)","note":"beta next Friday and GA at end of quarter"},{"id":"v070","label":"compatible","predicted":"contradiction","stage":"classification","confidence":0.88,"reason":"Billing states Quanta Retail invoices are due in 45 days while legal says a signed exception sets them at 60 days for the same customer.","note":"signed exception for marketplace invoices"},{"id":"v071","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #warehouse filtered out: no commitment signal (pure chatter)","note":"500 kg written as 0.5 tonnes"},{"id":"v072","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"shuttle hours plus an extra Friday route"},{"id":"v073","label":"compatible","predicted":"unrelated","stage":"prefilter","confidence":null,"reason":"message a in #product filtered out: no commitment signal (pure chatter)","note":"guided pilot before the end-of-quarter launch"},{"id":"v074","label":"compatible","predicted":"unrelated","stage":"matching","confidence":null,"reason":"matcher rejected the pair (different subject)","note":"coverage plus an explicit exclusion"}]}] -->
