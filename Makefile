# Convenience wrapper for macOS/Linux. The CLI is the source of truth:
#   uv run splitbrain --help
# There is no `make` on the developer's Windows machine; these targets are
# deliberately one-liners that mirror CLI commands exactly.

UV ?= uv run splitbrain

.PHONY: up down wipe bootstrap demo demo-offline record eval status seed run-all

up:
	$(UV) up

down:
	$(UV) down

wipe:
	$(UV) down --wipe

bootstrap:
	$(UV) bootstrap

demo:
	$(UV) demo --auto-decide

demo-offline:
	$(UV) demo --auto-decide --offline

record:
	$(UV) record

eval:
	$(UV) eval

status:
	$(UV) status

seed:
	$(UV) seed sso

run-all:
	$(UV) run all
