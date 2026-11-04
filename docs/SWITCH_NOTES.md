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
- Sequence numbers are large integers (> 2^53 is possible); store them as Python `int`, never as float.

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
  `sequence` of `9007194959773696` (> 2^53, Python `int`). `connection_state` carries
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
