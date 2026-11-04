# Build plan — milestones for the coding agent

Work **one milestone at a time**, in order. A milestone is done only when every acceptance check
passes on this machine (Windows 11, PowerShell or Git Bash). After each milestone: run
`uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not integration"`,
fix everything, commit with message `M<n>: <title>`, and stop to report.

Report format at the end of each milestone (in Spanish, short):
1. What you built (files).
2. The exact commands you ran and their real output (last lines).
3. Anything that did not work, anything you assumed, anything in SWITCH_NOTES that turned out different.

---

## M0 — Scaffold and stack control

- `git init` in `splitbrain/` (this folder is the repo root). `.gitignore`: `.venv/`, `__pycache__/`, `.splitbrain/`, `deploy/.env`, `*.db`, `.pytest_cache/`, `.ruff_cache/`.
- `pyproject.toml` (uv, package `splitbrain` under `src/`, console script `splitbrain = "splitbrain.cli:main"`), dependencies from SPEC §6, ruff config (`select = ["E","F","I","UP","B"]`, line-length 100), pytest config with marker `integration`.
- `deploy/docker-compose.yml` = exact copy of `../referencias/switch-upstream/deploy/local/standalone-docker-compose.yml`. `deploy/.env.example` = upstream `.env.example` with `SWITCH_VERSION=0.31.0`, `FRONTEND_BASE_URL=http://localhost:3000` and blank secrets.
- `config.py`: paths (repo root, `deploy/`, `.splitbrain/`), env loading (`python-dotenv`), typed settings. Missing required values raise.
- `cli.py` with argparse subcommands from SPEC §4.9 (stubs that raise `NotImplementedError("M<n>")` for later milestones) and working `up`, `down [--wipe]`, `status` (health only for now).
  - `up`: if `deploy/.env` is missing, create it from `.env.example` filling the secrets listed in SWITCH_NOTES "The stack" using `secrets.token_hex`. Run docker compose via `subprocess` with `-p splitbrain -f deploy/docker-compose.yml --env-file deploy/.env --profile collab --profile gateway up -d`. Poll `/health` (timeout 180 s) and `docker inspect` the setup container until it exited 0 (timeout 240 s). Print a clear success line with the URLs (Mattermost http://localhost:8065, Gateway http://localhost:3000).
- `LICENSE` Apache-2.0. `README.md` placeholder (one line).
- Tests: `.env` generation (all secrets filled, version pinned, no blank secret).

Acceptance:
- `uv sync` ok; `uv run splitbrain --help` lists every command.
- `uv run splitbrain up` → stack healthy; `uv run splitbrain status` prints `switch: ok` and the version 0.31.0 from `connection_state` or `/health`.
- `uv run pytest -m "not integration"` green.

## M1 — Switch protocol client

`src/splitbrain/switch/`:
- `sse.py`: pure incremental SSE parser (bytes/lines in → frames out: `id`, `event`, `data`; ignores comment lines; multi-line `data`). Unit tests incl. keepalive comments and split chunks.
- `events.py`: pydantic models for `connection_state`, `message`, `room_join`, `subscription_changed`, `gap`, `evicted`, `room_released`; unknown kinds parse to a generic frame and are logged, never crash. `sequence` as `int`.
- `client.py`: `SwitchAgent` (async):
  - `register(base_url, registration_token, name, description, overwrite)` classmethod → `(id, api_key)` (custom profile from SWITCH_NOTES).
  - `run(handler)`: open the stream with a UUID connection id kept for the process lifetime, `scope=all&filter=all&start_from=head`, send `Last-Event-ID` on reconnect, start the 2 s heartbeat after `connection_state`, reopen on beat 404/409 or socket drop (exponential backoff capped at 5 s), dispatch frames to `handler`. `gap` is logged and attached to the next event.
  - `op(name, **args)` → `result` or raises `SwitchOpError(status, body, op)`.
  - `act_in(room_id)` async context manager: takes the per-connection lock, `connect_to_room(room_id)`, yields; used for `post_message`, `create_room_document`, `define_role`, `assume_role`, ...
  - `post(room_id, body, thread_id=None)`, `targeted(room_id, body, target_names=None, target_roles=None, thread_id=None)` helpers built on `act_in`.
- `gateway.py`: `GatewayAdmin` (login cookie; `bridges()`; `set_greetings(bridge_id, enabled)`; `open_addressing(agent_id)`).
- `mattermost.py`: `MattermostAdmin` / `MattermostUser` (login, ensure user exists + in team, channel lookup by room name, post, reply in thread, read thread).

Tests: unit tests with `respx` for register/op/error mapping; parser tests; an **integration test** (`-m integration`, needs `splitbrain up`) that registers a temporary agent with a random name, creates a room with user `maria`, posts as maria through Mattermost **without mentioning the agent**, and asserts the agent receives the `message` event with `addressed == false`; then posts a threaded reply and asserts it appears in the Mattermost thread.

Acceptance: `uv run pytest -m integration -k switch` green against the running stack.

## M2 — Bootstrap and template

- `templates/splitbrain.template.yaml`: version-1 group document (SPEC §4.1): group "Acme", rooms with `channel_type`, `users`, `agents`; `splitbrain-ops` with `roles` (arbiter exclusive, verifier) whose instructions are the content of `agents/arbiter.md` / `agents/verifier.md` (inline them at bootstrap time via a `{arbiter_instructions}` param or by rendering), a `docs` entry "How Splitbrain works", and `links` ops → team rooms `watches`. Read `../referencias/switch-upstream/docs/TEMPLATES.md` ("The room block", "Groups") and `examples/room-templates/red-blue-workroom.template.yaml` first.
- `agents/sentinel.md`, `agents/arbiter.md`, `agents/verifier.md`: short role instructions in plain English (what the role does and never does, per SPEC §3–4).
- `bootstrap.py` (idempotent, safe to run twice):
  1. Register `splitbrain-sentinel`, `splitbrain-arbiter`, `splitbrain-verifier`, `splitbrain-arbiter-b` (overwrite) → `.splitbrain/state.json` (ids, api keys).
  2. Mattermost: ensure users maria, tomas, lucia, pablo, fabrizio exist with one generated password stored in state; all in team `switch`.
  3. Gateway: greetings off on the Mattermost bridge; `open_addressing` for every Splitbrain agent.
  4. Rooms: if the group's rooms don't exist yet (`list_all_rooms`), the Sentinel runs `create_room_from_yaml` with the template; then invite arbiter/verifier/arbiter-b where the template didn't. Record room ids in state.
  5. GitHub reference "Acme roadmap" (`create_reference` type `github`, value `{"urls": ["<SPLITBRAIN_ROADMAP_REPO url>"]}`) attached to `splitbrain-ops`.
  6. Print a summary: rooms, agents, and the Mattermost logins for the demo people.
- If anything in "Not yet verified" (SWITCH_NOTES) behaves differently, adapt, write down what you saw in `docs/SWITCH_NOTES.md` under a new heading "Verified in M2", and continue.

Acceptance: after `splitbrain up && splitbrain bootstrap` (twice), Mattermost shows channels sales, engineering (private, only tomas), support, finance, splitbrain-ops; `splitbrain status` lists the agents, rooms and the group; running bootstrap a second time changes nothing and does not fail.

## M3 — The brain (no Switch involved)

`src/splitbrain/llm/` and `src/splitbrain/core/` per SPEC §4.3, §4.4, §4.8:
- LLM client with live/record/replay and the per-item semantic cache; prompts; pydantic validation with one repair retry.
- prefilter, extractor (batched), SQLite store, matcher, classifier, packets (encode/decode `sb:<kind> {json}`), decision state machine (SPEC §4.6 step 5).
- `eval/dataset.jsonl` with ≥40 pairs per SPEC §4.11 (write them carefully; realistic workplace chat; mix English and a few Spanish lines) and `splitbrain eval`.
- Tests with a fake LLM (no network): prefilter (≥20 cases), matcher (same subject different room; same author skipped; different scope skipped; `*` scope matches), packets round-trip and rejection of bad lines, decision state machine (non-owner ignored, same person can't self-confirm, new proposal replaces pending), cassette miss raises in replay.

Acceptance: `uv run pytest -m "not integration"` green. `uv run splitbrain eval` with no API key fails loudly with a `ReplayMiss` message that explains what to do (until cassettes are recorded). With a key: `SPLITBRAIN_LLM_MODE=record uv run splitbrain eval` prints the metrics.

## M4 — Sentinel

- `agents/base.py` (shared run loop, logging, banner, graceful Ctrl+C), `agents/sentinel.py`, `tui.py` (rich Live view for the video: left column = incoming messages per room, dimmed when filtered; right column = claims and candidate links, highlighted when a candidate is sent).
- Behavior per SPEC §4.4. Candidate → `send_targeted_message` to role `arbiter` in `splitbrain-ops` with a readable summary + `sb:candidate` line.

Acceptance: stack + bootstrap running, `splitbrain run sentinel --tui` in one terminal, `splitbrain seed sso` in another → within 20 s a candidate message appears in `splitbrain-ops` in Mattermost; the near-misses scenario produces no candidate.

## M5 — Arbiter and Verifier

Per SPEC §4.5 and §4.6: role lease (exclusive `arbiter`; `arbiter-b` stands by and takes over when A stops), evidence request/response, verdict, conflict room creation, links, decision record document, brief, decision protocol, `sb:decided`. Verifier live (GitHub) and fixture modes; `seed/github_fixture.json` with the SSO issue and a few unrelated issues.

Acceptance: with sentinel + arbiter + verifier running, `splitbrain seed sso --auto-decide` → a conflict room with maria and tomas exists, has links to sales and engineering, the brief and the record; after the auto-decision the record says DECIDED. Killing the Arbiter and starting `arbiter-b` → `splitbrain status` shows arbiter-b holding the role.

## M6 — Consent and corrections

Per SPEC §4.7. The engineering room is private, so the SSO scenario must go through consent (`--auto-decide` also answers the consent question as tomas: "yes"). Corrections appear as thread replies under the original messages in sales and engineering. `sb:corrected` closes the loop in the record.

Acceptance: full SSO loop end to end, verified by reading the Mattermost threads through the API in an integration test.

## M7 — One-command demo and replay

`splitbrain demo` per SPEC §4.9 with banners; `splitbrain record`; scenarios `refunds`, `hackathon` (template `templates/hackathon.template.yaml`), `near-misses`; cassettes recorded and committed; reproducible from a clean clone: `git clone` → `uv run splitbrain demo --auto-decide` works with **no API key** (replay) and with fixture evidence.

Acceptance: from a fresh clone in a temp folder, after `splitbrain down --wipe`: `uv run splitbrain demo --auto-decide` reaches "Corrections posted" with no API key set.

## M8 — README and polish

README in this order (SPEC/proposal): one sentence + GIF placeholder of the moment the room is created; 3-command quick start; "How we use Switch" (feature → file → why); architecture diagram (Mermaid); evaluation results; known limits (replay mode, fixture evidence, Mattermost demo, tasks not used). Plus `docs/BLOG_DRAFT.md` skeleton.
