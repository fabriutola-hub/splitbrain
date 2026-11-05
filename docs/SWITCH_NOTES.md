# Switch 0.31.0 — verified facts

Everything on this page was **run against a real local Switch 0.31.0 stack** on
2026-11-04 (Gate 1), or read from the upstream source in
`../referencias/switch-upstream`. Where this page and the upstream source
disagree, the source wins; where they and your memory disagree, this page wins.
Logs of the probes: `../orquestacion/logs/gate1-probe*.log`.

Upstream docs worth reading (paths relative to the repo root `D:\FlipTheSwitch`):

- `referencias/switch-upstream/docs/official/internals/agent-protocol.md` — the wire protocol (authoritative)
- `referencias/switch-upstream/docs/official/internals/rooms-and-resources.md`
- `referencias/switch-upstream/docs/official/internals/identity-and-access.md`
- `referencias/switch-upstream/docs/TEMPLATES.md` — sections "The room block", "Groups"
- `referencias/switch-upstream/core/switch_core/bridges/agent/operations/definitions.py` — every operation's exact signature
- `referencias/switch-upstream/deploy/local/standalone-docker-compose.yml`

## The stack

- Images are published to GHCR. **Pin `SWITCH_VERSION=0.31.0`** (latest published on 2026-11-04; `gateway` and `setup` exist at that tag too). The compose file refuses to start without it.
- Start: `docker compose -p <project> --profile collab --profile gateway up -d` with the standalone compose file and a `.env` next to it.
- `.env` = upstream `.env.example` with these secrets filled with random hex: `DB_PASSWORD DB_OWNER_PASSWORD AGENT_REGISTRATION_TOKEN GATEWAY_ADMIN_PASSWORD MATTERMOST_ADMIN_PASSWORD MATTERMOST_USER_PASSWORD` (24 random bytes hex each) and `SECRET_KEYS=local:<32 random bytes hex>`. Set `FRONTEND_BASE_URL=http://localhost:3000`.
- Ports (all bound to 127.0.0.1): Switch API + agent bridge + gateway API `8000`, Gateway UI `3000`, Mattermost `8065`, Postgres `5432`.
- `GET http://127.0.0.1:8000/health` → `{"status":"ok"}` (public).
- The `setup` container seeds Mattermost (admin user `admin`, team `switch`, user `user`), registers the Mattermost bridge **as the default bridge**, links `admin@switch.local` to Mattermost user `user`, prints `Setup complete!` and exits 0. Wait for that exit before bootstrapping.
- Cold start on this PC: ~40 s after images are pulled.

## Registering our own agents (custom protocol clients)

```
POST /agents
Authorization: Bearer <AGENT_REGISTRATION_TOKEN>
{"name": "splitbrain-sentinel", "description": "...", "connector_type": "custom",
 "integration_profile": {"connection_model": "always_on", "message_exchange": true,
   "pre_invocation_mediation": [], "post_invocation_mediation": [], "event_reporting": []},
 "overwrite": false}
→ 200 {"id": "<uuid>", "api_key": "<secret, returned once>"}
```

- Verified working. Re-registering an existing name is 409 unless `"overwrite": true` (then a new api key is issued).
- Names must match `^[a-z0-9][a-z0-9._-]*$`.
- The owner of agents registered with the registration token is a Switch user named **"Agent Bootstrap"**.
- Every later call uses `Authorization: Bearer <api_key>`.

## Gateway admin calls (bootstrap only)

Cookie session on the **same port 8000**:

- `POST /gateway/auth/login` `{"email": GATEWAY_ADMIN_EMAIL, "password": GATEWAY_ADMIN_PASSWORD}` → 200 + session cookie. Verified.
- `GET /gateway/collaborations` → list of bridges (`display_name`, `id`, `agent_greetings_enabled`, ...). Verified.
- `PATCH /gateway/collaborations/{bridge_id}` `{"agent_greetings_enabled": false}` → 200. Verified. **Do this**: otherwise Switch posts "Hey! Ping @agent and I'll jump in." in every room an agent joins, which breaks Splitbrain's "silent by default" rule.
- `PUT /gateway/agents/{agent_id}/addressing-policy` `{"policy": null}` → 200. Verified. A new agent starts **owner-only**; Mattermost users (maria, tomas, ...) are unclaimed platform accounts and match no rule, so without this they could not address our agents and Switch would auto-reply a refusal on the agent's behalf. Splitbrain enforces "only the conflict's owners can close it" itself, in the Arbiter.

## Mattermost users (demo people)

Mattermost REST API at `http://127.0.0.1:8065/api/v4`:

- Login: `POST /users/login {"login_id","password"}` → token in the `Token` response header.
- Create user (as admin): `POST /users {"username","email","password","first_name","last_name"}`; add to team: `POST /teams/{team_id}/members {"team_id","user_id"}`; team id from `GET /teams/name/switch`. Verified.
- Post as a user: `POST /posts {"channel_id","message"}` (and `"root_id"` to reply in a thread). Verified.
- List a user's channels: `GET /users/me/teams/{team_id}/channels`. A Switch room appears as a channel whose `name` is the room name (a suffix like `-4a491dca` is added when the name already exists).
- Read a thread: `GET /posts/{post_id}/thread`.

## The event stream

```
GET /agents/{agent_id}/events?connection_id=<uuid>&scope=all&filter=all&start_from=head
Authorization: Bearer <api_key>
Accept: text/event-stream
```

- Verified: with `scope=all` + `filter=all`, **a message a person posts in Mattermost without mentioning the agent arrives** as `event: message` with `payload.addressed=false`. This is the core of the Sentinel.
- First frame is `connection_state` (verified fields: `connection_id, agent_id, generation, scope, filter, spawn_capable, rooms, cursor, position, protocol (=9), heartbeat_interval_seconds (=2.0), server{version: "0.31.0", ...}`).
- `subscription_changed {"rooms":[...], "reason": "..."}` arrives when the covered/claimed set changes (e.g. after `create_room` or `connect_to_room`).
- Domain events carry an SSE `id:` line = `sequence`. Keep the last one and send it as `Last-Event-ID` on reconnect, **with the same connection_id**.
- Keepalives are SSE comment lines (start with `:`), every 15 s of silence. Ignore them.
- Verified `message` frame:

```json
{"type":"message","room_id":"228aa2f4-...","bridge_id":"7d7e3ee5-...","channel_type":"channel_public",
 "payload":{"addressed":false,
   "sender":"@switch-mattermost-7d7e3ee5-...-maria:localhost","sender_name":"maria",
   "sender_kind":null,"on_behalf_of":null,
   "message_id":"sw_0b67fc41dfe64da2d59615952fe64ea5",
   "body":"Le confirmé a Acme SSO para el 1 de diciembre.",
   "timestamp":1793776781000,"thread_id":null,"attachments":[]},
 "sequence":9007194959773697}
```

- `channel_type` is `channel_public` or `channel_private` (verified both).
- `sender_name` is the Mattermost username for people and the agent name for agents. Treat `sender` as opaque.
- Our own posts and other agents' posts also arrive on the stream: **filter out messages whose `sender_name` is one of our agent names**, and anything with `sender_kind == "platform"`.
- `room_join` frames: `{"member","member_name","timestamp","listening"}`. Ignore them except for logging.
- Sequence numbers are large integers (observed just below 2^53; store as int because the protocol does not bound it) — use Python `int`, never `float`.

## Heartbeat

`POST /agents/{agent_id}/connection/beat {"connection_id": "...", "cursor": <last sequence or 0>}` every 2 s (TTL 6 s). 200 = alive. **404 or 409 = reopen the stream** (same connection id), not back off. A beat is refused while no stream is attached, so start beating only after `connection_state` arrives.

## Operations

```
POST /agents/{agent_id}/ops/{name}
Authorization: Bearer <api_key>
X-Switch-Connection-Id: <connection id>      (needed by ops that act on "the connected room")
<arguments object, unwrapped>
→ 200 {"result": ...}
```

400 bad args (unexpected keys are rejected too — send only declared parameters), 403 permission, 404 unknown op, 409 dead connection. `GET /agents/{agent_id}/ops` lists the 53 operations with schemas.

Verified calls and their results:

| Operation | Args used | Result |
|---|---|---|
| `create_room` | `name, description, agent_names, user_names, channel_type` | `{"id","name","transport_room_id","failed_attachments"}`. Room is bridged to Mattermost (default bridge) and the channel appears there with the users in it. The owner's linked account (`user`) and the system `admin` also join. |
| `connect_to_room` | `room_id` | room context: `participants` (id, name, type `agent`/`user`, status, room_role, alias), instructions, references, roles, linked rooms. Claims the room for this connection. |
| `add_users_to_room` | `room_id, user_names` | `{"ok":true,"added":["tomas"],"unresolved":[]}` |
| `define_role` | `name, instructions, exclusive` | `{"status":"defined","name":"arbiter"}` (acts on the connected room) |
| `assume_role` | `role` | `{"role":"arbiter","instructions":"..."}`; `get_room_detail` then shows `held_by` |
| `create_room_document` | `name, description, instructions, content` | `{"document_id": "..."}` (connected room) |
| `post_message` | `body`, optional `thread_id` | `{"event_id": "sw_..."}` (connected room) |
| `read_context` | `limit, room_id` | `{"threads":[{"root":{id,kind,sender,sender_name,body,timestamp,attachments},"replies":[...]}]}` |
| `list_rooms` | — | list of `{"room_id","name","description","connected","archived"}` (**key is `room_id`, not `id`**) |
| `get_room_detail` | `room_id` | `channel_type, bridge_id, external_channel_id, group_name, agent_names, connected_user_names, roles[{name, exclusive, held_by[...]}]`, ... |
| `list_reference_types` | — | confluence, github, google_drive, jira (closed set) |

### Acting in many rooms from one connection — verified

One `scope=all` connection can **listen to every room and act in any of them**:
`connect_to_room(A)` → `post_message(...)` → `connect_to_room(B)` → `post_message(..., thread_id=X)`.
Events from all rooms keep arriving while the claim moves. Because "the connected room" is
connection state, **serialize every connect+act sequence with one asyncio.Lock per connection**.

### Threads — verified

`post_message(body, thread_id=<switch message_id of the root message>)` shows up in
Mattermost as a reply inside that post's thread. The root's Switch id is the `payload.message_id`
of the original `message` event. If the original message was itself a reply, use its
`payload.thread_id` instead.

### Direct post without a connection

`POST /agents/{agent_id}/message {"room_id","content"}` → `{"ok":true,"event_id":...}`. No thread support. Use only where a thread is not needed.

## Not yet verified (verify in integration tests, fail loud)

- `send_targeted_message(body, target_names | target_roles, thread_id)` between our own agents — expected to arrive with `payload.addressed=true` for the target.
- `link_rooms(source_room_id, target_room_id, label)` when the caller is a member of only one of the rooms. If it is refused, have the Sentinel (member of every room) create the links.
- `create_room_from_yaml(yaml, inputs)` with a version-1 `group:` + `rooms:` + `links:` document, called by an agent.
- `create_reference(type="github", name, description, instructions, value={"urls":[...]})` + `attach_reference_to_room`.
- `update_room_document` by the creating agent.
- Exclusive role contention between two different agents (second `assume_role` should fail while the first holds the lease).

## Limits that shape the design (from the upstream docs)

- Tasks (`delegate_task` & co.) are present but **not ready for use**. Do not build on them.
- An agent edits only room documents it created.
- An agent holds at most one role lease, globally.
- Reference types are a closed set: Google Drive, Confluence, GitHub, Jira.
- Slack does not render Markdown tables — every chat message must read well as plain text. Mattermost renders Markdown, but keep messages table-free anyway.

## Verified in M0 (2026-11-04, against the compose project `splitbrain`)

- The M0 stack starts with `-p splitbrain --profile collab --profile gateway --env-file deploy/.env`;
  containers are named `splitbrain-<service>-1`. `setup` exits 0 and `/health` answers before the
  stack is usable. All images were already cached locally (`switch-core`, `gateway`, `setup` at
  tag `0.31.0`, `postgres:16-alpine`, `mattermost-team-edition:11.9.0`).
- **`GET /health` returns exactly `{"status":"ok"}`** (HTTP 200, no version field, no extra headers
  carrying a version). `GET /version` (agent bridge) and `GET /gateway/version` are authenticated:
  without credentials both answer 401 `{"detail":"Not authenticated"}`.
- TASKS.md M0 asks `status` to print the version "from `connection_state` or `/health`". Neither is
  available in M0: `connection_state` needs an agent stream (M1), and `/health` carries no version.
  **Simplest fix that keeps "fail loud":** `POST /gateway/auth/login` with
  `{"email": GATEWAY_ADMIN_EMAIL, "password": GATEWAY_ADMIN_PASSWORD}` (verified 200 on both ports
  8000 and 3000) returns `{"...,"server":{"version":"0.31.0","contracts":{...}}}`. `status` reads
  `server.version` from that authenticated server declaration; if the field is absent it raises
  instead of printing a guessed version. M1 can switch to `connection_state.server.version`.
- **Local HTTP calls must ignore proxy env.** This machine sets
  `HTTP_PROXY=HTTPS_PROXY=http://127.0.0.1:4057` and no `NO_PROXY`. With httpx's default
  `trust_env=True`, a `POST /gateway/auth/login` issued after a `GET /health` on the same client
  returned 401 `Missing or invalid Authorization header` (from the agent bridge's bearer
  middleware), while a fresh-client POST or curl returned 200. `httpx.AsyncClient(trust_env=False)`
  fixes it deterministically. **Scope of the fix (orchestrator rule, M1):** `trust_env=False`
  applies ONLY to clients that talk to loopback (Switch, Gateway, Mattermost, stack health).
  Internet-facing clients (GitHub API, the LLM) keep httpx's default `trust_env=True` so they
  work both inside this sandbox and on a normal machine. M1 centralizes this in
  `config.loopback_client()`.
- The Docker CLI is **not on PATH** here (`docker` is not found in Git Bash or PowerShell); the
  executable is `D:\Docker\DockerDesktop\resources\bin\docker.exe` (Docker 29.9.2, Compose
  v5.6.1). M0 resolves it with `shutil.which`, two standard Windows install paths and a
  `SPLITBRAIN_DOCKER` override.
- The upstream `.env.example` has three deliberately blank active keys that are **not** required
  secrets: `CONTROLLER_TOKEN_SECRET` (only with the `agent_management` flag), `FEATURE_FLAGS_ENABLED`
  (a flag) and `JWT_SECRET_KEY` (legacy, "a new .env leaves it empty"). The Gate 1 stack ran with
  exactly those blanks. `splitbrain up` fills only the seven real secrets listed above.
- The upstream `LICENSE` is Apache 2.0 **plus a "Commons Clause" restriction**; Splitbrain ships a
  plain Apache-2.0 `LICENSE` instead.

## Verified in M1 (2026-11-04, live `splitbrain` stack, `it-` temporary resources)

- `POST /agents` with the custom `integration_profile` from "Registering our own agents" returns
  200 `{"id","api_key"}`. `PUT /gateway/agents/{id}/addressing-policy {"policy": null}` returns
  200 for a freshly registered `it-` agent.
- **`GET /gateway/collaborations` returns a JSON list whose elements use `bridge_id`, not `id`.**
  Verified live: keys include `bridge_id`, `display_name`, `agent_greetings_enabled`,
  `is_default`, `bridge_type`, `room_count`. The "Gateway admin calls" section above says `id`;
  the upstream source (`gateway/schemas.py::BridgeDetail`) and the server say `bridge_id`, so the
  source wins. `GatewayBridge` accepts both. M2 must use `bridge_id`.
- **A `scope=all&filter=all` stream does not emit `subscription_changed` on `create_room` alone.**
  On this stack the frame arrives when the connection claims the room with `connect_to_room`
  (`{"rooms":["<room id>"],"reason":"subscription updated"}`). Gate 1's log shows the frame
  right after `create_room` because that probe also connected to the room. The M1 integration
  test claims the room explicitly before posting.
- After claiming, a Mattermost post that does **not** mention the agent arrives as `event: message`
  with `payload.addressed=false`, `sender_name` = the Mattermost username, `channel_type` and a
  `sequence` of `9007194959773696` (observed just below 2^53; store as int because the
  protocol does not bound it). `connection_state` carries
  `server.version="0.31.0"`, `protocol=9`, `heartbeat_interval_seconds=2.0`. Control frames
  (`connection_state`, `subscription_changed`, ...) have **no `type` field in their data** — the
  SSE `event:` name is the kind; domain events carry both. Keepalives are bare `:` comments.
- `post_message` with `thread_id` set to the root event's `payload.message_id` shows up as a reply
  in the Mattermost thread read through `GET /api/v4/posts/{post_id}/thread` (verified end to end).
- Mattermost: `GET /users/username/{name}` → 404 for a new user; `POST /users` → 201;
  `POST /teams/{team_id}/members` → 201 (409 when already a member). The bridged channel needs
  about a second to settle after creation; the integration test waits 1 s before posting.
- `splitbrain status` keeps M0's authenticated gateway-login version lookup: M1 can read
  `connection_state.server.version` once an agent is connected, but no agent credentials exist
  until M2's bootstrap, and registering a throwaway agent just to print the version is wasteful.
  `SwitchAgent.server_version` already exposes it for M2+.
- M1 integration resources are `it-agent-*`, `it-user-*`, `it-room-*`; no reserved demo name is
  touched, and no destructive operation is used, so they remain in the stack after the test.

## Verified in M2 (2026-11-04, live `splitbrain` stack, bootstrap run twice)

- **An op carrying `X-Switch-Connection-Id` for a connection with no open stream is refused with
  409** `{"detail":"connection … is not open; reconnect and resume from where you got to"}`.
  `create_room_from_yaml` must therefore be called while a stream is attached: bootstrap keeps one
  short-lived Sentinel connection (waiting for `connection_state`) for the whole run. Ops that need
  no room (`get_room_detail`, `list_all_rooms`, …) work **with the header omitted**; M1's
  `SwitchAgent.op(..., connection=False)` does that, and `splitbrain status` uses it.
- **The live 0.31.0 operation registry differs from the source tree.** `GET /agents/{id}/ops`
  shows `list_all_rooms` accepts only `include_archived` (not the source's `limit`/`cursor`) and
  returns a **bare list** of rooms (18 on this stack), not `{"rooms":[…],"next_cursor":…}`.
  `create_room_from_yaml` accepts `yaml` + `inputs`; `create_reference`,
  `attach_reference_to_room`, `invite_agent_to_room`, `link_rooms`, `connect_to_room`,
  `get_room_detail`, `list_reference_types` and `list_all_references` match the source. Bootstrap
  calls `list_all_rooms` with no arguments and handles both list and dict shapes. Never add an
  argument to an op without reading the live registry first.
- **`create_room_from_yaml` with a version-1 `group:` + `rooms:` + `links:` works when called by an
  agent.** It returned `{group_id, group_name, rooms:[{room_id, room_name, failed_attachments,…}],
  errors:[]}`. The template created group "Acme" with 5 rooms, the `arbiter` (exclusive) and
  `verifier` roles with the instructions from `agents/*.md` supplied through required multiline
  params in `inputs`, the room document "How Splitbrain works", and **all four `watches` links**
  from `splitbrain-ops` to the team rooms. Verified through `connect_to_room(ops).linked_rooms`
  (each entry has `target_room_id`, `target_room_name`, `label`, `access`). Because the template
  creates the links server-side, **`link_rooms` was never needed**; the "Not yet verified" question
  about calling `link_rooms` while the caller is a member of only one room remains open.
- **`create_reference(type="github", …, value={"urls":[…]})` + `attach_reference_to_room` work.**
  `list_reference_types` includes `github`. `connect_to_room(ops).references` returns the attached
  reference with its full `value.urls` = `SPLITBRAIN_ROADMAP_REPO` from `.env.local`
  (`https://github.com/fabriutola-hub/splitbrain-demo-roadmap`). Bootstrap reuses an existing
  reference by name and attaches only when it is missing.
- `invite_agent_to_room` works: the template names sentinel/arbiter/verifier in `splitbrain-ops`,
  and bootstrap invited `splitbrain-arbiter-b`; `get_room_detail(ops).agent_names` now has all four.
- `get_room_detail` confirms `engineering` is `channel_private` with `connected_user_names=['tomas']`;
  `sales` has `['lucia','maria']`; every room has `group_name='Acme'`. `splitbrain-ops` has
  `connected_user_names=[]` because the template names no `users:` (SPEC §4.1: the operator's
  linked account joins automatically). Roles are unheld until M5.
- **Mattermost channel visibility**: as `maria` → `off-topic (O), town-square (O), sales (O)`; as
  `tomas` → `off-topic (O), town-square (O), engineering (P)`. Neither sees the other's private or
  unrelated rooms, and neither sees `splitbrain-ops`. The five demo channels exist; the acceptance
  line "Mattermost shows channels …" refers to the operator/admin view.
- Gateway `set_greetings(bridge_id, False)` is confirmed by a later `GET /gateway/collaborations`
  (`agent_greetings_enabled=False` on the default Mattermost bridge). All four agents had their
  addressing policy opened **before** any room was created, so no "Hey! Ping @…" greeting appeared.
- **State and idempotency**: `.splitbrain/state.json` is written after each step. A first failed
  run had already created Mattermost users with a password that was never saved, so M1's
  `MattermostAdmin.ensure_user` now repairs that with
  `PUT /api/v4/users/{id}/password {"new_password": …}` (admin) when the user's login returns 401.
  Running bootstrap twice produced the **same state.json hash**, with no duplicate rooms, users or
  references and no agent key rotation (existing keys are verified through `GET /agents/{id}/ops`).
- Hackathon rooms (`hackathon-prizes`, `hackathon-judging`) are deliberately not created in M2:
  TASKS.md assigns their template to M7. The user `fabrizio` is created now, as M2 requires.

## Verified in M4 (2026-11-04, live `splitbrain` stack, `SPLITBRAIN_LLM_MODE=record`)

- **`send_targeted_message` with `target_roles=["arbiter"]` works while nobody holds the role.**
  Verified in a temporary `it-m4-probe-*` room (role defined, zero holders) and in
  `splitbrain-ops`: it returns `{"event_id": "sw_…", "target_statuses": {}}` and posts the body
  prefixed with `@arbiter `. So the Sentinel can publish `sb:candidate` in M4, before M5's Arbiter
  assumes the exclusive lease. The "Not yet verified" item about *delivery to another live agent*
  still needs M5; room delivery and role-target resolution are now verified.
- **`read_context(room_id=…, limit=…, connection=False)` works with no stream attached** and returns
  `{"threads", "truncated", "oldest_timestamp"}`; `threads` is oldest-first, so the tail is freshest.
  Used for the acceptance reads. `list_rooms(connection=False)` returns the agent's own rooms
  (the 5 Acme rooms plus two bridged Mattermost defaults) with `room_id, name, connected, archived`.
  `list_all_rooms(connection=False)` returns a **bare list**; neither call includes `channel_type`
  (get it from the `message` frame or `get_room_detail`).
- **Coverage of a `scope=all&filter=all` stream is empty at open.** A fresh `connection_state` on
  this stack reports `rooms=[]`; each `connect_to_room` emits exactly one `subscription_changed`
  with `reason="subscription updated"` and a single-element `rooms` list. Claiming the 5 Acme rooms
  produced 5 such frames. Confirms M1's note: a room created or joined after the stream opens is not
  covered until it is claimed (or the stream is reopened). M4 claims the demo rooms on
  `connection_state`, and claims new ids on `subscription_changed`, our own `room_join` or an
  unknown `room_id` on a message.
- **`start_from=head` with a new connection id does not replay old messages on process restart.**
  Nothing from the previous run was redelivered, so `processed_messages` / `pairs_seen` in
  `.splitbrain/sentinel.db` are the real idempotency guard (re-injecting the 9 old message ids
  made 0 model calls, 0 posts and left all four table counts unchanged).
- **rich on Windows**: this machine sets `TERM=dumb`, which makes `rich.live.Live` skip every
  refresh (only the banner appeared). `Console(force_terminal=True, legacy_windows=False,
  _environ={TERM: xterm-256color})` fixes it; `legacy_windows=False` is also needed because rich
  otherwise reserves one column (a `Console(width=120)` renders at 119). Verified 120x32, 30 lines.
- **Cassette collision**: the extraction cache is keyed by normalized message text, so `record`
  overwrites an existing cassette when a seed message is byte-identical to an eval line. Two
  `near-misses` lines matched eval pair `n01` and rewrote those M3 cassettes with live `sw_…`
  message ids and slightly different `value`s. They were restored from HEAD; `splitbrain eval
  --mode replay` still reports p=1.000 r=0.889 f1=0.941 because those two claims are rejected by
  the matcher on scope before classification. Avoid exact eval wording in new seed scenarios.
- **SPEC §3.3 changed during M4** (orchestrator edit at 06:54): a private-room quote must never be
  posted in `splitbrain-ops`, in the readable text or in the packet. The Sentinel now substitutes
  `#room (private), author: quote withheld until the author consents` plus the extracted subject
  and value, and emits `"text": null, "text_withheld": true` for that claim. **Contradiction to
  record:** the new note says `splitbrain-ops` is `channel_private` and that "the template sets
  this", but `templates/splitbrain.template.yaml` still declares `channel_type: channel_public`
  and the live `get_room_detail` confirms `channel_public`. The template is M2's file and the spec
  itself says the change only takes effect after `down --wipe && up && bootstrap`; M4 did not wipe
  the stack or edit the template. **Simplest fix that keeps the product rule:** redact in the
  Sentinel, so the rule holds even with a public ops room. Raised for the orchestrator.
- **M5 packet contract**: because `Claim.text` is a non-nullable `str` and `Claim` uses
  `extra="forbid"`, a raw `sb:candidate` body must NOT be fed straight into
  `Candidate.model_validate()` — the withheld claim carries `text: null` and `text_withheld: true`.
  M5 needs a tolerant packet model (or a matching change to `core/models.py`).
- **No delete operation exists** (by design), so the pre-fix candidate `sb-8126`, which contained
  the verbatim engineering quote, is still in `splitbrain-ops` history. A `down --wipe` +
  `bootstrap` clears it before recording the video.

## Step 0 / Verified in M5 (2026-11-04, live `splitbrain` stack, clean wipe)

Step 0: `templates/splitbrain.template.yaml` now declares
`splitbrain-ops: channel_private` (SPEC §3.3). After
`uv run splitbrain down --wipe && uv run splitbrain up && uv run splitbrain bootstrap`,
`get_room_detail` reports `splitbrain-ops channel_type=channel_private`, with
`agent_names` = sentinel, arbiter, verifier, arbiter-b and `connected_user_names=[]`.
This resolves the contradiction M4 recorded (the §4.1 table still says "public"; the
product rule in §3.3 wins). No Sentinel-side exception is needed for ops to be private.

- **Exclusive role contention is real.** With two live streams on
  `splitbrain-arbiter` and `splitbrain-arbiter-b`, `assume_role("arbiter")` succeeded
  for A and was refused for B with **HTTP 400**
  `{"detail":"Role 'arbiter' is exclusive and currently held by another agent"}`;
  `get_room_detail(ops).roles[arbiter].held_by` stayed `['splitbrain-arbiter']`.
  After A's stream was closed, B's retries kept failing until **6.7 s** after the
  first refusal — the heartbeat TTL is 6 s — then B's `assume_role` returned 200 and
  `held_by` became `['splitbrain-arbiter-b']`. `release_role` returns `{"status":"released"}`
  and clears `held_by`. So the 5 s standby retry is the right interval.
- **The lease survives room hops.** After A assumed `arbiter` in ops, a
  `connect_to_room(<other room>)` left `held_by` intact with
  `{"name":"splitbrain-arbiter","present_here":false,"session_room":"<other room>"}`.
  The Arbiter can therefore create/claim conflict rooms without losing the lease.
- **`send_targeted_message` between two live agents works.** Called by the Arbiter in
  ops with `target_roles=["verifier"]`, it returned
  `{"event_id":"sw_…","target_statuses":{"splitbrain-verifier":"live"}}`; the Verifier's
  `scope=all&filter=all` stream received an `event: message` with
  `payload.addressed=True`, `sender_name="splitbrain-arbiter"` and a body prefixed
  `@verifier `. `target_names=["splitbrain-sentinel"]` behaves the same way. This closes
  M4's "delivery to another live agent" question.
- **`link_rooms` works when the caller is NOT a member of the target room.** Verified
  from a room created by `splitbrain-arbiter` linking to `sales` and `engineering`:
  both calls returned 200 with `{target_room_id, target_room_name,
  target_room_description, label}`. `connect_to_room(conflict).linked_rooms` then lists
  both entries with the exact labels and `access: "not_member"`. The Arbiter's own
  `connect_to_room(sales)` is still refused with HTTP 400
  `{"detail":"Agent is not a member of this room"}` — but linking does not require
  membership. **Simplest fix that keeps the product rule:** the Arbiter creates the links
  itself; the `sb:link_request` / `sb:linked` packet fallback to the Sentinel is
  implemented but was not needed on this server.
- **`create_room` (live) returns `id`, `name`, `transport_room_id`, `matrix_room_id`,
  `failed_attachments`** — no `caller_is_member` key from the source docs. With
  `user_names=["maria","tomas"]` the bridged Mattermost channel appears with exactly
  those people; `get_room_detail` confirms it. `create_room_document` returns
  `document_id`, `update_room_document` by the same agent returns
  `{"document_id":…,"status":"ok"}`, and `connect_to_room(room).documents` lists it.
- **`connect_to_room` needs a live session even for reads.** Calling it with
  `connection=False` (no `X-Switch-Connection-Id`) fails with **HTTP 400**
  `{"detail":"MCP session has no session id; cannot connect to room"}`. Room-agnostic
  ops (`list_all_rooms`, `get_room_detail`, `read_context(room_id=…)`) work without a
  stream; reading documents/links needs a short-lived stream that claims the room.
- **`connect_to_room(ops).references` shape**: a list of
  `{id,type,name,description,instructions,value:{"urls":[…]}}`. The Verifier reads the
  repo URL from there, never from chat text. `roles` in the same payload carries
  `held_by` objects `{name,present_here,session_room}`.
- **GitHub live evidence**: `GET /search/issues?q=repo:fabriutola-hub/splitbrain-demo-roadmap SSO in:title,body`
  returns open #2 and #1; `GET /repos/…/issues/2/timeline` returns
  `milestoned Q4 2026` → `demilestoned Q4 2026` → `milestoned Q1 2027` (all 2026-11-04).
  `seed/github_fixture.json` is recorded from the same repo with
  `uv run python scripts/record_github_fixture.py` (5 open issues + timelines).
- **End-to-end M5 smoke** (`SPLITBRAIN_LLM_MODE=record`, evidence live, four agents):
  `seed sso` produced candidate `sb-7266` in ops **without** the engineering quote,
  the Verifier answered with the Q4→Q1 2027 move, the Arbiter posted
  `sb:verdict confirmed`, asked `sb:consent_request` with a short test timeout, and
  created `conflict-sb-7266-sso` with maria/tomas, both `origin:` links, the
  `SB-7266 decision record` (Status: OPEN) and the plain-text brief. Killing the
  Arbiter made `splitbrain status` report `arbiter role: splitbrain-arbiter-b`.

## Verified in M6 (2026-11-04, live `splitbrain` stack, `SPLITBRAIN_LLM_MODE=record`)

- **Consent works in the author's own thread.** `send_targeted_message` with
  `target_names=["splitbrain-sentinel"]` delivers `sb:consent_request` (verified
  M5). The Sentinel replies with `post_message(thread_id=<root Switch message id>)`
  in `#engineering`; Mattermost shows it as reply [2] of
  `GET /api/v4/posts/{root}/thread`. The seed's "yes" arrives on the Switch stream
  as a `message` frame whose `payload.thread_id` equals that same root id and
  whose `sender_name` is the Mattermost username, so matching on
  `(room_id, thread_id, author)` is exact. The Sentinel's own question in that
  thread is ignored (different sender); only the next reply by that author decides.
- **`sb:consent` carries the verbatim quote only when granted.** Readable ops text
  says "Consent granted ... The verbatim quote is attached in the packet"; the
  private quote appears only inside the packet JSON, never in `sb:candidate` and
  never in the conflict room before consent. `splitbrain-ops` is itself
  `channel_private` after Step 0.
- **Two links, brief and record verified through the API.** `connect_to_room(conflict).linked_rooms`
  returned exactly `origin: #sales (maria)` and `origin: #engineering (tomas)`;
  `get_room_detail` returned `people=['maria','tomas']`,
  `agents=['splitbrain-arbiter','splitbrain-sentinel']`. The brief quotes both
  claims and the evidence; `load_internal_documents` shows `Status: DECIDED`,
  the decision text, proposer/confirmer, and the final line
  `Corrections posted in #sales, #engineering`.
- **Corrections are thread replies.** `GET /api/v4/posts/{id}/thread` for the
  sales root returned `[original, "Update: @maria and @tomas resolved ..."]`; the
  engineering root returned `[original, consent question, "yes", correction]`.
  No correction is a top-level post in a team room.
- **`seed sso --auto-decide` closed the loop in one command**: it found the consent
  question, answered "yes" as tomas, waited for `conflict-sb-7552-sso`, posted
  `decision: ...` as maria and `confirm` as tomas, then waited for the Arbiter's
  `Corrections posted in #sales, #engineering.` confirmation.
- **`seed near-misses` reaches nobody.** After it ran, `read_context(ops)` still
  held exactly the same 4 `sb:candidate` packets (all from SSO runs), no new
  `sb:consent_request` / `sb:decided`, and no new conflict room. The Sentinel log
  shows `No alert: compatible (confidence 0.90): A December beta and Q1 general
  availability are two phases of one rollout` and `Extracted 0 claim(s)` for the
  question and the hypothetical.
- **Failover**: killing the Arbiter produced `arbiter role: unheld` at t+2s and
  `arbiter role: splitbrain-arbiter-b` at t+4s via `splitbrain status`.
- **Live evidence vs fixture**: the acceptance run used
  `SPLITBRAIN_EVIDENCE_MODE=live` (GitHub REST, issue #2 Q4 2026 → Q1 2027 on
  Nov 4). The end-to-end integration test used `fixture`, which printed the exact
  banner `EVIDENCE: fixture (recorded GitHub data)` and produced the same summary.
  A live network failure raises `SplitbrainEvidenceError` with a message naming
  the repo, the failure and `SPLITBRAIN_EVIDENCE_MODE=fixture`; it never falls back
  silently.
- **Runtime-state caveat (repeat runs).** Claims stay `active` in
  `.splitbrain/sentinel.db`, so re-seeding `sso` without a wipe can pair a new
  message with an old active claim and create a second candidate whose correction
  lands in the previous run's thread. That is expected for a persistent store,
  not a Switch behaviour. `splitbrain down --wipe` clears it for the demo, and the
  end-to-end integration test isolates itself by pointing `sentinel.DB_FILENAME`
  at a fresh per-run database.
- **`AgentRuntime.serve` needed a stop watcher.** With a `scope=all` stream idle
  between 15 s keepalives, `await stream` never noticed a set `stop` event
  (`_stream_once` only checks `stop` when a parsed frame arrives). `serve()` now
  waits on the stream task *and* `stop.wait()` with `FIRST_COMPLETED`, then cancels
  the stream. Without this, in-process agents hung the integration suite on
  shutdown; with it, `pytest -m integration -q` finishes in ~25 s.
- **Cassette hygiene**: the two `near-misses` lines that were byte-identical to
  eval pair `n01` were reworded. After all `record` runs, none of the 11 changed
  extraction cassettes holds text from `eval/dataset.jsonl`; the three changed
  classification cassettes differ only in `recorded_at`.

## Verified in M7 (2026-11-04, live `splitbrain` stack, clean wipe)

### Possible upstream bug: race in the EXCLUSIVE role lease

Reproduce with `uv run python scripts/probe_arbiter_lease.py` after
`uv run splitbrain up && uv run splitbrain bootstrap`, with no Arbiter running:

1. Wait until `get_room_detail(splitbrain-ops).roles[arbiter].held_by == []`
   (the heartbeat TTL is 6 s after the previous holder stops).
2. Open one `scope=all&filter=all` SSE stream for `splitbrain-arbiter` and one
   for `splitbrain-arbiter-b`; call `connect_to_room(splitbrain-ops)` on each.
3. Fire both `assume_role("arbiter")` calls in the same `asyncio.gather`.
4. Read `get_room_detail(splitbrain-ops)` (no connection header).

Observed on **two consecutive runs** (probe run twice, 2026-11-04 ~10:10 -04:00):

```
held_by BEFORE: []
assume_role('arbiter') splitbrain-arbiter:   HTTP 200 -> {'role': 'arbiter', 'instructions': '# Arbiter\n\nYou hold the exclusive arbiter role in splitbrain-ops. Only one Arbiter acts at a time.\n...'}
assume_role('arbiter') splitbrain-arbiter-b: HTTP 200 -> {'role': 'arbiter', 'instructions': '# Arbiter\n\nYou hold the exclusive arbiter role ...'}
held_by AFTER simultaneous assume: ['splitbrain-arbiter-b', 'splitbrain-arbiter']   (run 1)
held_by AFTER simultaneous assume: ['splitbrain-arbiter', 'splitbrain-arbiter-b']   (run 2)
RESULT: exclusive lease granted to TWO agents (server race).
release_role() splitbrain-arbiter-b: HTTP 200 -> {'status': 'released'}
held_by AFTER loser released: ['splitbrain-arbiter']
held_by AFTER cleanup: []
```

So Switch 0.31.0 granted an **exclusive** role to two different agents when both
`assume_role` calls landed in the same instant. This contradicts the M5
observation only in timing: when A already holds the lease, B is still refused
with HTTP 400 `{"detail":"Role 'arbiter' is exclusive and currently held by
another agent"}` (verified again in M5). The list order in `held_by` is not
stable, so any client-side tie-break must sort names, not trust the array order.
`release_role()` takes **no arguments**, needs a connected room, is idempotent,
and releases only the calling agent's lease (A survived B's release).
**To report upstream** with the exact steps above.

Consequence seen in the first M7 demo: both Arbiters posted `sb:evidence_request`
/ `sb:verdict` / `sb:consent_request` and both called `create_room` with the same
`conflict-sb-5526-sso` name. Switch **allows duplicate room names** (Mattermost
gets a suffixed channel); `list_all_rooms` then returned two entries with that
name. The standby's `connect_to_room` on its own room failed with HTTP 400
`{"detail":"Agent is not a member of this room"}` because `create_room` always
names `splitbrain-arbiter` + `splitbrain-sentinel`, not the caller's own name.

**Fix kept in Splitbrain (does not hide the server behaviour):**
`Arbiter._claim_lease()` re-reads `held_by` *after* `assume_role`, keeps only the
alphabetically first holder, and makes every other holder call `release_role`
and return to standby; the check is repeated before acting on **every**
`sb:candidate`. `_open_conflict` looks the room name up with `list_all_rooms`
first and reuses it instead of creating a second one. `demo` starts `arbiter-b`
only after `splitbrain-arbiter`'s lease is confirmed (fallback: >= 8 s delay).
The demo's multi-room read is only a defence with a visible `WARNING`, never a
substitute for these three guards. Failover still works: when the winner's
heartbeat lapses, `held_by` contains only the standby and it takes over.

### Other M7 facts

- **`create_room_from_yaml` with `inputs={}` works** for a second, parameter-free
  version-1 group document. `templates/hackathon.template.yaml` created group
  `Flip the Switch` with `hackathon-prizes` and `hackathon-judging` (both
  `channel_public`, users `page-prizes`/`page-judging`/`fabrizio`, agent
  `splitbrain-sentinel`, one link labelled `same event`). Running bootstrap a
  second time found both rooms by name and created nothing.
- **Mattermost `TeammateNameDisplay` is `full_name`** on this stack, so setting
  `first_name`/`last_name`/`nickname` through `PUT /api/v4/users/{id}/patch`
  renders "Prizes page" / "Judging page" in the UI. Verified through
  `GET /api/v4/users/username/{name}` and each user's channel list.
- **Evidence lookup needs the `subject_key` fallback.** The live model extracts
  `subject="refund approval threshold"`, `subject_key="refunds"`; a GitHub search
  for the literal subject finds nothing, so the Verifier now tries the subject,
  the canonical key and the subject's words (`snapshot_any`). Issue #5 is then
  found in both `live` and `fixture` mode (`status=conflicting`, so the Arbiter
  confirms). `sso` still matches on its first term ("SSO").
- **The hackathon pages are not in the demo repo.** A GitHub lookup honestly
  returns no issues, which would discard the case. `seed/scenario_evidence.json`
  is an explicitly labelled, opt-in scenario fixture (paraphrases of the two
  public pages), enabled by `SPLITBRAIN_SCENARIO_EVIDENCE=hackathon` and
  announced with a `[DEGRADED]` banner. No GitHub issue was invented; item URLs
  are `scenario-fixture:` identifiers, not fake web links.
- **Record/replay from a clean environment**: `uv run splitbrain record`
  refreshed 94 extraction and 35 classification cassettes (eval: 44 pairs,
  p=1.000 r=0.889 f1=0.941; `sso`=1, `refunds`=1, `hackathon`=1,
  `near-misses`=0 candidates). `uv run splitbrain eval --mode replay` produced
  the same metrics with no network. No seed message is byte-identical to any
  `eval/dataset.jsonl` line (checked before every record run).
- **Windows `zoneinfo`** has no system IANA database and no `tzdata`, so
  `ZoneInfo("America/Caracas")` raised `ZoneInfoNotFoundError`. `tzdata>=2024.1`
  is now a dependency; `SPLITBRAIN_TZ` then yields `Nov 4 03:19 UTC-04:00`
  instead of a bare UTC hour. An invalid zone raises at startup.
- **Fixture banner carries the `[DEGRADED]` prefix** since M7; M6's exact string
  `EVIDENCE: fixture (recorded GitHub data)` is now
  `[DEGRADED] EVIDENCE: fixture (recorded GitHub data, no network)`.
- **Clean-clone reproducibility (acceptance check, verified twice).** After
  `git clone D:\FlipTheSwitch\splitbrain <temp>` (no `.env.local`, no
  `deploy/.env`, no `SPLITBRAIN_*` variables, no `.venv`) and
  `splitbrain down --wipe` in the original, `uv run splitbrain demo --auto-decide`
  in the clone reached `Corrections posted` and printed the summary with exit
  code 0: `[DEGRADED] LLM replay (no SPLITBRAIN_LLM_API_KEY)` plus live GitHub
  evidence. Repeating with `--offline` also exited 0, with both
  `[DEGRADED] LLM replay` and `[DEGRADED] EVIDENCE: fixture` at startup and in
  the final summary. `uv run` created the clone's `.venv` and installed the 28
  locked packages (including `tzdata`) without any manual step. Conflict ids
  differed between runs (`sb-0471`, `sb-2046`) because Switch message ids are
  fresh after each wipe; the loop was identical.
