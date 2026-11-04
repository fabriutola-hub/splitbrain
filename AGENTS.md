# AGENTS.md — rules for any coding agent working in this repo

You are building **Splitbrain** for the Flip the Switch hackathon. The orchestrator (Claude) writes
the specs, reviews every milestone, and runs the checks; you write the code.

## Read first, every time

1. `docs/SPEC.md` — what we build and why. The product rules in §3 are non-negotiable.
2. `docs/SWITCH_NOTES.md` — facts about Switch 0.31.0 verified against a real server. Trust it over
   your memory. Switch is new (released 2026-08-26); you have probably never seen its API.
3. `docs/TASKS.md` — the milestone you were asked to do. Do only that milestone.
4. When you need more detail on Switch, read the upstream source in
   `../referencias/switch-upstream/` (read-only; never modify it). The operation signatures are in
   `core/switch_core/bridges/agent/operations/definitions.py`.

## Where you may write

Only inside `D:\FlipTheSwitch\splitbrain\`. Never write in `../referencias/`, `../orquestacion/`
or `../assets/`. Never touch Docker containers, volumes or networks other than the compose project
`splitbrain`.

## How to work

- Plan briefly, then implement. Small files, clear names, type hints everywhere.
- After writing code, **run it**. Never claim something works without having run the command and
  seen the output. Paste the real output in your report.
- Run `uv run ruff check . --fix`, `uv run ruff format .`, `uv run pytest -m "not integration"`
  before you report. Integration tests (`-m integration`) need the stack (`uv run splitbrain up`).
- Commit at the end of each milestone: `git add -A && git commit -m "M<n>: <title>"`.
- If something in the spec is impossible or contradicts what the server does, do not silently
  work around it: write what you observed in your report and in `docs/SWITCH_NOTES.md`, choose the
  simplest fix that keeps the product rules, and say so.

## Code rules

- Python 3.12+, fully async with `asyncio` + `httpx`. Pydantic v2 models for every payload.
- **Fail loud, never fake.** Missing config → raise. Unexpected HTTP status → raise with the
  operation name, status and body. No bare `except:`; `except Exception` only in event loops,
  and it must log the traceback. Degraded modes (replay, fixture) print a banner.
- No secrets in the repo, logs or exceptions (API keys, passwords, tokens). `deploy/.env` and
  `.splitbrain/` are gitignored.
- Chat messages are untrusted data. Never `eval`, never run commands from chat text, never let
  chat text choose an operation. In prompts, wrap chat text in `<message>` data blocks.
- No destructive Switch operations (no delete of rooms, documents, roles, references).
- Chat output must read well as plain text (no Markdown tables).
- Comments explain non-obvious intent only. No comments narrating the change.
- Code, identifiers, logs, README: English. Your reports to the orchestrator: Spanish.

## Environment

Windows 11. Shells: PowerShell and Git Bash. `uv` 0.11, Python 3.12/3.14, Docker Desktop 29,
Node 24, git, gh. There is no `make` on this machine: the `splitbrain` CLI is the entry point.
Use `pathlib` and `subprocess` with argument lists (no shell strings) so it runs on any OS.
