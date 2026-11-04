# Splitbrain — product and technical spec

Hackathon: **Flip the Switch** (WeMakeDevs × Switch by SandboxAQ). Track 1, Best Business
Workflow. Submission deadline: Saturday 2026-11-07, 11:59 PM IST (2:29 PM Caracas). We freeze
features Friday night.

Judging: Switch usage 30% (is Switch central?), technical execution 25% (does it work, can it be
cloned and reproduced?), creativity & impact 25%, presentation 20% (video + README).

## 1. One sentence

Splitbrain is a set of agents on Switch that notice when two teams in a company believe
incompatible things, verify it, and bring the two responsible people into one room to decide —
before the mistake reaches a customer.

## 2. The story the demo tells

1. `#sales` — María (Sales): "Confirmed with Acme: SSO will be live for them on December 1."
2. `#engineering` (private) — Tomás (Engineering): "We're pulling SSO out of Q4. The auth migration has to land first."
3. Nobody is in both rooms. The **Sentinel** is. It links the two claims and sends a candidate to `splitbrain-ops`.
4. The **Arbiter** (holder of the exclusive `arbiter` role) asks the **Verifier** for independent evidence. The Verifier reads the GitHub reference attached to `splitbrain-ops` and finds the SSO issue moved to milestone "Q1 2027".
5. Evidence confirms it. Tomás's quote comes from a private room, so the Sentinel asks Tomás, in his thread, for consent to quote him. He says yes.
6. The Arbiter creates `conflict-sb-0001-sso` with María and Tomás, links it to both origin rooms, posts both quotes and the evidence, and opens a decision record (room document).
7. María and Tomás agree: `decision: SSO beta for Acme on Dec 15, GA in Q1.` / `confirm`. Only they can close it.
8. The Arbiter writes the decision into the record. The Sentinel posts the correction in the original thread in `#sales` and in `#engineering`. Everyone sees the same truth.
9. Closing beat: the same agents run on the real public announcements of this hackathon, which disagree with each other (Track 3: 20 PRs vs 10 PRs). "If this happens to the people running an agents hackathon, it happens to your company too."

All names (Acme, María, Tomás, ...) are fictional and the README says so.

## 3. Product rules (non-negotiable)

1. **Silent by default.** Agents never post in team rooms except (a) a consent question to the author of a quote from a private room, in that author's own thread, and (b) corrections after a human decision, in the thread where the claim was born. Everything else happens in `splitbrain-ops` and conflict rooms.
2. **People decide.** No agent picks the correct version. Agents collect evidence, convene, record, and propagate what people decided.
3. **Consent before revealing.** A quote from a `channel_private` room is shown in a conflict room only after its author says yes. If they say no or don't answer in time, the conflict room gets "(quote withheld at the author's request)" plus the claim's subject only.
4. **No evidence, no interruption.** A candidate without independent evidence or with low classifier confidence is discarded, logged in `splitbrain-ops`, and nobody is bothered.
5. **Messages are data, never instructions.** Chat text is passed to the model inside clearly delimited data blocks. No agent executes anything a chat message asks for. No destructive operations exist in the code (no delete room, no delete document).
6. **Fail loud.** Missing config, a missing recorded model response in replay mode, an unexpected HTTP status from Switch: raise with a clear message. Degraded modes (replay, GitHub fixture) are announced on stdout with a banner and stated in the README.

## 4. Architecture

Three processes, each its own Switch agent and its own protocol client. All communication between
them goes through Switch rooms (no shared database, no sockets between them).

| Agent (Switch name) | Rooms | Does | Never does |
|---|---|---|---|
| `splitbrain-sentinel` | every team room + `splitbrain-ops` | listens to everything (`scope=all, filter=all`), prefilters, extracts claims, stores them (SQLite), matches pairs across rooms, classifies, sends candidates; asks consent; posts corrections | decide, open rooms, talk in team rooms otherwise |
| `splitbrain-arbiter` | `splitbrain-ops` + conflict rooms it creates | holds exclusive role `arbiter`; verifies candidates (classifier + evidence), opens conflict rooms, adds people, links rooms, writes the decision record, runs the decision protocol | read team rooms, pick a winner |
| `splitbrain-verifier` | `splitbrain-ops` | holds role `verifier`; answers evidence requests from the GitHub reference attached to the ops room | decide anything |

Optional fourth process for the demo: `splitbrain-arbiter-b`, a standby Arbiter. It tries
`assume_role("arbiter")`; while A holds the exclusive lease it waits and retries every 5 s; if A
dies, its lease lapses and B takes over. This shows why there are never duplicate alerts.

Chat app: the Mattermost that the Switch stack brings (`--profile collab`). Reproducible by anyone
with Docker. Slack/Discord can be connected later through the Gateway; nothing in Splitbrain
depends on Mattermost specifically, except the demo seeding script, which posts as people through
the Mattermost API.

### 4.1 Rooms (created by the template in one pass)

Room group **"Acme"** containing:

| Room | channel_type | People | Agents |
|---|---|---|---|
| `sales` | public | maria, lucia | sentinel |
| `engineering` | private | tomas | sentinel |
| `support` | public | lucia | sentinel |
| `finance` | public | pablo | sentinel |
| `splitbrain-ops` | public | (the operator's linked account joins automatically) | sentinel, arbiter, verifier |

`splitbrain-ops` carries: roles `arbiter` (exclusive) and `verifier` (not exclusive) with the
instructions in `agents/arbiter.md` / `agents/verifier.md`; a GitHub reference "Acme roadmap"; a
room document "How Splitbrain works". Links: `splitbrain-ops` → each team room, label `watches`.

The hackathon scenario adds two public rooms, `hackathon-prizes` and `hackathon-judging`
(people: `fabrizio`), created by the same template or a second one.

Conflict rooms are created at runtime by the Arbiter: name `conflict-sb-<4 digits>-<subject slug>`,
public, people = the two claim authors, agents = arbiter (and sentinel, so it can post the
correction acknowledgements there). Linked to each origin room with label
`origin: #<room> (<author>)`.

### 4.2 Message packets between agents

Agents exchange structured data inside normal chat messages so humans watching `splitbrain-ops`
can read the conversation. Each such message is plain human-readable text, followed by **one final
line**:

```
sb:<kind> <compact JSON>
```

`kind` ∈ `candidate`, `evidence_request`, `evidence`, `verdict`, `consent_request`, `consent`,
`decided`, `corrected`. A message has at most one packet line. Parsing is strict: unknown kind or
invalid JSON → log a warning and ignore the message. Packets are only accepted from our own
agent names (check `sender_name`).

Delivery: `send_targeted_message` in `splitbrain-ops` with `target_roles=["arbiter"]` (Sentinel →
Arbiter), `target_roles=["verifier"]` (Arbiter → Verifier), `target_names=["splitbrain-sentinel"]`
(Arbiter → Sentinel). Replies go in the same thread when there is one.

### 4.3 Data model (pydantic, stored in SQLite by the Sentinel)

```json
Claim {
  "id": "clm_0142",
  "room_id": "<switch room id>", "room_name": "sales", "channel_type": "channel_public",
  "message_id": "sw_...", "thread_id": "sw_... | null",   // where to correct = thread_id or message_id
  "author": "maria", "ts": 1793776781000,
  "text": "<original message body>",
  "kind": "commitment | decision | policy | status | other",
  "subject": "SSO", "subject_key": "sso",                 // subject_key: lowercase slug, canonical
  "scope": "Acme", "scope_key": "acme",                   // customer/segment/region; "*" when global
  "value": "available on 2026-12-01",
  "polarity": "affirm | negate",
  "effective_date": "2026-12-01 | null",
  "confidence": 0.0-1.0,
  "status": "active | superseded | resolved"
}
Candidate { "id": "sb-0001", "claim_a": Claim, "claim_b": Claim,
            "relation": "contradiction", "confidence": 0.91, "reason": "...", "created_at": ... }
Evidence  { "candidate_id", "source": "github | fixture", "status": "supports_a | supports_b | conflicting | none",
            "items": [{"title","url","state","milestone","labels","updated_at"}], "summary": "..." }
Decision  { "candidate_id", "room_id", "text", "proposed_by", "confirmed_by", "decided_at" }
```

SQLite file: `.splitbrain/sentinel.db`. Tables: `claims`, `candidates`, `processed_messages`
(idempotency by message_id), `pairs_seen` (never re-surface the same pair). Plain `sqlite3`
from the standard library.

### 4.4 Detection pipeline (Sentinel)

1. **Prefilter** (no model): drop messages from our agents, `sender_kind == "platform"`, messages in `splitbrain-ops` and `conflict-*` rooms, fewer than 5 words, and pure chatter. Keep a message if it contains any commitment signal: a date or weekday or month name, a quarter (`Q1`–`Q4`), a number with a unit/currency/percent, or a commitment/decision verb (promise, confirm, commit, ship, launch, release, deliver, cut, drop, pull, delay, move, postpone, cancel, change, policy, refund, deadline, guarantee, will, won't, no longer; plus Spanish equivalents: prometí, confirmé, sale, lanzamos, recortamos, sacamos, movemos, posponemos, cancelamos, cambia, política, reembolso, plazo). Unit tested with ≥20 examples.
2. **Extraction** (model, batched up to 8 messages or 2 s): message → 0..n claims with the Claim fields above. The model normalizes `subject_key` and `scope_key` (lowercase slugs; same thing ⇒ same key, e.g. "single sign-on" ⇒ `sso`).
3. **Matching** (no model): for a new claim, find stored claims with status `active`, a **different room**, the **same subject_key** (or rapidfuzz `token_set_ratio(subject) ≥ 88`), and compatible scope (same `scope_key`, or either is `*`). Skip pairs already in `pairs_seen`. Skip pairs by the same author (a person updating their own decision is an update, not a conflict).
4. **Classification** (model): pair → `{relation: contradiction | update | compatible | unrelated, confidence, reason}`. `reason` is one short sentence a human can read.
5. **Candidate**: `relation == contradiction` and `confidence ≥ 0.7` → create Candidate, send `sb:candidate` to the Arbiter. Anything else → log only (TUI + `splitbrain-ops` is NOT used for these; silence).

Near-misses the classifier must reject (and the eval dataset must contain): same feature for a
different customer; a person correcting their own earlier statement; same subject but compatible
values ("beta Dec 1" vs "GA in Q1"); a later message from the same team that already supersedes;
hypotheticals ("if we pull SSO..."); questions ("are we still shipping SSO?").

### 4.5 Verification (Arbiter + Verifier)

On `sb:candidate`:
1. Arbiter posts in `splitbrain-ops` (thread = the candidate message): `Verifying SB-0001...` and sends `sb:evidence_request {candidate_id, subject, subject_key, scope, claim_a: {room, value, date}, claim_b: {...}}` to role `verifier`.
2. Verifier answers in the thread with a human summary + `sb:evidence {...}` (Evidence model). Source:
   - `live`: GitHub REST API (`GET /search/issues?q=repo:<owner>/<repo> <subject> in:title,body`, then each issue's milestone). Repo comes from the GitHub reference attached to `splitbrain-ops` (`connect_to_room` result lists references). Unauthenticated works for public repos; use `GITHUB_TOKEN` if set.
   - The live demo repo exists: **https://github.com/fabriutola-hub/splitbrain-demo-roadmap** (public, fictional data). Issues: #1 "Auth service migration to the new identity provider" (Q4 2026), **#2 "SSO (SAML / OIDC) for enterprise customers" — milestoned Q4 2026, then moved to Q1 2027 on 2026-11-04 with a comment from Tomás**, #3 "Audit log export to CSV" (Q4 2026), #4 "Dark mode for the admin console" (Q1 2027), #5 "Support macros: refunds over $250 now need manager approval" (Q4 2026). #6 is a closed duplicate; ignore closed issues.
   - Milestone moves come from `GET /repos/{owner}/{repo}/issues/{n}/timeline` (events `demilestoned` / `milestoned` with `milestone.title` and `created_at`). Verified: #2 shows `milestoned Q4 2026` → `demilestoned Q4 2026` → `milestoned Q1 2027`. Put "moved from Q4 2026 to Q1 2027 on Nov 4" in the evidence summary.
   - `fixture`: `seed/github_fixture.json`, the same data recorded from the live repo (same shape as the live provider's output). Banner: `EVIDENCE: fixture (recorded GitHub data)`.
3. Arbiter verdict: **confirmed** iff classifier confidence ≥ 0.7 **and** evidence status ≠ `none`. Otherwise **discarded**. Post `sb:verdict` in the thread. Discarded ⇒ done, nobody else hears about it.
4. Confirmed ⇒ if either claim's `channel_type` is `channel_private`, send `sb:consent_request {candidate_id, claim_id, author}` to the Sentinel and wait for `sb:consent` (timeout `SPLITBRAIN_CONSENT_TIMEOUT_S`, default 600). Then open the conflict room.

### 4.6 The conflict room (Arbiter)

1. `create_room(name, description, agent_names=["splitbrain-arbiter","splitbrain-sentinel"], user_names=[author_a, author_b], instructions=<rules>)`.
2. `link_rooms(conflict → origin room, label "origin: #sales (maria)")` for both origins (if refused, ask the Sentinel; see SWITCH_NOTES "Not yet verified").
3. `connect_to_room(conflict)`, `create_room_document("SB-0001 decision record", ...)` with: both quotes (or "withheld"), links/ids of the origin messages, the evidence summary, status `OPEN`.
4. Post the brief (plain text, no tables):
   ```
   @maria @tomas — Splitbrain found two statements that can't both be true.

   #sales, María, Nov 4 10:02: "Confirmed with Acme: SSO will be live for them on December 1."
   #engineering, Tomás, Nov 4 10:05: "We're pulling SSO out of Q4. The auth migration has to land first."

   Evidence (GitHub, acme/roadmap): issue #42 "SSO for enterprise" moved to milestone "Q1 2027" on Nov 3.

   You two decide. When you agree, one of you writes:  decision: <what you agreed>
   and the other replies:  confirm
   I'll record it and correct both original threads.
   ```
5. **Decision protocol** (state machine, unit tested): only the two authors count. `decision: <text>` (also `decisión:`) from one of them sets `proposed`; `confirm` / `confirmo` / `agree` / `de acuerdo` from **the other** author sets `decided`. A new `decision:` replaces a pending proposal. Anyone else trying gets one reply: "Only @maria and @tomas can close this conflict." Model is not used here — people's words are recorded verbatim.
6. On `decided`: `update_room_document` (status `DECIDED`, decision text, who proposed/confirmed, time), post "Recorded. Correcting the original threads now.", send `sb:decided {candidate_id, decision, conflict_room, origins: [{room_id, thread_id}]}` to the Sentinel.
7. On `sb:corrected` from the Sentinel: append "Corrections posted in #sales and #engineering" to the record and post a one-line confirmation in the conflict room.

### 4.7 Corrections and consent (Sentinel)

- **Consent**: on `sb:consent_request`, `connect_to_room(origin)` and `post_message(thread_id=claim thread)`: `@tomas Splitbrain found that this message conflicts with a statement from another team. May I quote it in a private resolution room with @maria? Reply "yes" or "no" here.` The next reply in that thread **by that author** decides (yes/sí/ok ⇒ granted; no ⇒ denied). Answer the Arbiter with `sb:consent`.
- **Correction**: on `sb:decided`, for each origin: `connect_to_room(origin)` → `post_message(thread_id=origin thread)`: `Update: @maria and @tomas resolved a conflict about SSO for Acme in #conflict-sb-0001-sso. Decision: "SSO beta for Acme on Dec 15, GA in Q1." Please use this from now on.` Mark both claims `resolved`, store the decision as a new claim with status `active`, reply `sb:corrected` to the Arbiter.

### 4.8 Model layer

- One OpenAI-compatible client (httpx, no SDK): `POST {SPLITBRAIN_LLM_BASE_URL}/chat/completions`, `temperature: 0`, `response_format: {"type": "json_object"}`. Default base URL `https://openrouter.ai/api/v1`, default model **`tencent/hy4`** (Tencent Hy4 GA, 1M context). Key: `SPLITBRAIN_LLM_API_KEY`. Any OpenAI-compatible endpoint works by changing the env vars. Optional `SPLITBRAIN_LLM_REASONING_EFFORT` (e.g. `none`) is sent as `reasoning_effort` when set. If a response has `reasoning_content`, ignore it; parse only `choices[0].message.content`.
- Config precedence: process environment > `.env.local` (repo root, gitignored, the developer's keys) > defaults. The developer's `.env.local` uses River AI: base URL `https://api.river.ai/v1`, model `deepseek-ai/DeepSeek-V4.1-Flash-1017`, `SPLITBRAIN_LLM_REASONING_EFFORT=none`. The cassette files record which model produced them.
- Verified 2026-11-04 against River AI: `POST https://api.river.ai/v1/chat/completions` with `model=deepseek-ai/DeepSeek-V4.1-Flash-1017`, `reasoning_effort=none`, `response_format={"type":"json_object"}` → HTTP 200 in ~1.7 s, valid JSON in `choices[0].message.content`, no `reasoning_content`. **With a vague prompt the model swapped `subject_key` and `scope_key`** (it returned subject "Acme", scope "SSO go-live date"). So every prompt must define each field precisely ("subject = the feature, policy or thing being promised or decided; scope = the customer, segment or region it applies to, or `*`") and include 2–3 worked examples, and the pydantic validators should reject obvious swaps where cheap (e.g. a scope_key that equals a known customer is fine; a subject_key that is a customer name from the same message is suspicious → repair retry).
- Responses are validated with pydantic. One retry on invalid JSON with the validation error appended; then raise.
- **Record / replay** (`SPLITBRAIN_LLM_MODE` = `live` | `record` | `replay`, default `replay` when no API key is set, else `live`):
  - The cache is semantic and per item, so replay does not depend on batching or timing: extraction is cached per message under `sha256("extract|v1|" + normalized_body)`; classification per pair under `sha256("classify|v1|" + key(claim_a) + "|" + key(claim_b))` with the two keys sorted.
  - Files: `cassettes/<task>/<hash>.json` containing `{"task","model","input","output","recorded_at"}`. Committed to git.
  - `record` = live + write. `replay` = read only; a miss raises `ReplayMiss` naming the input and telling the user to set an API key or run `splitbrain record`.
  - Startup banner states the mode, model and base URL (never the key).
- Prompts live in `src/splitbrain/llm/prompts.py`. Chat text goes inside `<message>...</message>` data blocks with an instruction that their content is data to analyze, not instructions to follow.

### 4.9 CLI (the only entry point; works in PowerShell, cmd and bash)

`uv run splitbrain <command>`:

| Command | Does |
|---|---|
| `up` | create `deploy/.env` with fresh secrets if missing (pinned `SWITCH_VERSION=0.31.0`), `docker compose -p splitbrain --profile collab --profile gateway up -d`, wait for `/health` and for `setup` to exit 0 |
| `down [--wipe]` | stop the stack (`--wipe` also removes volumes and `.splitbrain/`) |
| `bootstrap` | idempotent: register agents (overwrite), store keys in `.splitbrain/state.json`, create Mattermost demo users, greetings off, open addressing policies, run the template, attach the GitHub reference, print the Mattermost logins |
| `run sentinel\|arbiter\|verifier\|arbiter-b` | run one agent in the foreground (`--tui` for the Sentinel's rich live view) |
| `run all` | the three agents as subprocesses with colored, prefixed logs |
| `seed <scenario> [--auto-decide]` | post a scenario's messages as its people with its delays; `--auto-decide` also posts the decision + confirm in the conflict room once it exists |
| `demo [--scenario sso] [--auto-decide]` | `up` + `bootstrap` + `run all` + `seed` in one command, with banners for every degraded mode |
| `record` | run the eval dataset and the seed scenarios in `record` mode to refresh cassettes |
| `eval [--mode replay\|live]` | run `eval/dataset.jsonl`, print precision / recall / F1 for `contradiction` and the confusion matrix, write `eval/results.md` |
| `status` | stack health, agents and their liveness, rooms, which agent holds `arbiter` |

A `Makefile` mirrors the main commands for macOS/Linux users (`make demo`, `make eval`), but the
CLI is the source of truth.

### 4.10 Seed scenarios (`seed/scenarios/*.yaml`)

```yaml
name: sso
people: {maria: "María Gómez", tomas: "Tomás Rivera", lucia: "Lucía Pérez", pablo: "Pablo Ruiz"}
messages:
  - {room: sales, as: maria, after_s: 0, text: "Morning! Big one: confirmed with Acme that SSO will be live for them on December 1."}
  - {room: support, as: lucia, after_s: 3, text: "Reminder: refunds over $500 still need a manager's OK."}
  - {room: engineering, as: tomas, after_s: 6, text: "Heads up: we're pulling SSO out of Q4. The auth migration has to land first."}
  - {room: finance, as: pablo, after_s: 4, text: "Q4 budget review moved to Thursday."}
decision:            # used by --auto-decide
  propose: {as: maria, text: "decision: SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today."}
  confirm: {as: tomas, text: "confirm"}
```

Scenarios: `sso` (the hero), `refunds` (support quotes an old refund policy finance changed),
`hackathon` (the closing beat), `near-misses` (only non-conflicts; nothing must reach a human).

### 4.11 Evaluation

`eval/dataset.jsonl`, at least 40 labeled pairs, one per line:
`{"id","a":{"room","author","text"},"b":{...},"label":"contradiction|update|compatible|unrelated","note"}`
with at least 12 contradictions and 12 near-misses (section 4.4). `splitbrain eval` runs
extraction + matching + classification on each pair exactly as the Sentinel does and reports
precision/recall/F1 for `contradiction`, the confusion matrix, and every error with its reason.
Results go into `eval/results.md` and the README.

## 5. Repository layout

```
splitbrain/
├── AGENTS.md  CODEBUDDY.md  README.md  LICENSE (Apache-2.0)  Makefile  pyproject.toml  uv.lock
├── deploy/            docker-compose.yml (upstream standalone, pinned), .env.example
├── src/splitbrain/
│   ├── cli.py  config.py  bootstrap.py  seed.py  tui.py
│   ├── switch/        sse.py  events.py  client.py  gateway.py  mattermost.py
│   ├── llm/           client.py  cassette.py  prompts.py
│   ├── core/          models.py  prefilter.py  extractor.py  store.py  matcher.py  classifier.py  packets.py  decision.py
│   ├── evidence/      github.py
│   └── agents/        base.py  sentinel.py  arbiter.py  verifier.py
├── agents/            sentinel.md  arbiter.md  verifier.md   (role instructions, shown in Switch)
├── templates/         splitbrain.template.yaml  hackathon.template.yaml
├── seed/              scenarios/*.yaml  github_fixture.json
├── cassettes/         extract/  classify/
├── eval/              dataset.jsonl  results.md
└── tests/             unit tests; integration tests marked `integration` (need the stack)
```

## 6. Tech choices

Python 3.12 (`requires-python = ">=3.12"`), managed with `uv`. Dependencies: `httpx`, `pydantic>=2`,
`pyyaml`, `rich`, `rapidfuzz`, `python-dotenv`. Dev: `pytest`, `pytest-asyncio`, `respx`, `ruff`.
Fully async (`asyncio`). No other frameworks. The code must run on Windows 11 (the developer's
machine) and on macOS/Linux (the judges').
