# Blind evaluation pairs (v3)

`dataset-v3.jsonl` contains 60 newly authored, independent workplace-chat pairs, using the v2
schema and relation definitions. Each pair stands alone; messages in other pairs provide no context.
For each case, the relation and its semantic explanation were chosen before drafting the messages,
without trying to anticipate a system's answer.

Dataset references were limited to the v2 protocol, the first five v2 rows for the JSON schema,
and the original dataset for label style. The repository README was read only through Evaluation.
Only the existing v2 loader test was consulted for the loader's public import and return fields.
No implementation, other test bodies, cassettes, scripts, or result reports were inspected.
Targeted text searches of existing `eval/*.jsonl` checked that the invented companies, products,
author handles, and room names did not occur there; no additional v2 examples were viewed.

The cases cover prices and billing bases, dates, service commitments, capacities, policies, units,
relative deadlines, approvals, authorized exceptions, self-corrections, explicit team replacements,
release phases, and unrelated messages sharing words. Authorized exceptions are `compatible`;
different customers or other independent scopes are `unrelated`, following the v2 protocol.

| Label | Pairs |
| --- | ---: |
| contradiction | 20 |
| update | 10 |
| compatible | 15 |
| unrelated | 15 |
| **Total** | **60** |

Language counts are 42 `en`, 12 `es`, and 6 `mixed`: 18 pairs (30%) contain Spanish. Each mixed
pair has one Spanish and one English message. Labels are interleaved: the first 30 pairs contain
10 contradictions, 5 updates, 7 compatible pairs, and 8 unrelated pairs; the last 30 contain
10, 5, 8, and 7 respectively. Each half has 21 English, 6 Spanish, and 3 mixed pairs.

All cases, including labels and notes, are frozen before the first evaluation. Labels will not
change after any run. Authoring and structural verification do not run the prefilter or evaluation
pipeline on v3. Comparing the old and new prefilters is a separate live evaluation; its errors
must be reported against these fixed labels.
