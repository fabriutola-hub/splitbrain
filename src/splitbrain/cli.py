"""The only entry point: `uv run splitbrain <command>`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from typing import Any

from . import bootstrap, demo, evaluation, recording, seed, stack
from .agents import arbiter as arbiter_agent
from .agents import sentinel as sentinel_agent
from .agents import verifier as verifier_agent
from .config import Settings, SplitbrainError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="splitbrain",
        description="Control the local Switch 0.31.0 stack and the Splitbrain agents.",
        epilog=(
            "First run on any OS (uv + Docker required):\n"
            "  uv run splitbrain demo --auto-decide\n"
            "  uv run splitbrain demo --auto-decide --recovery\n"
            "  uv run splitbrain eval\n"
            "  uv run splitbrain status\n"
            "Run 'splitbrain <command> --help' for the full options of a command."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="<command>",
        title="commands",
        description="Every command works in PowerShell, cmd and bash.",
    )

    commands.add_parser(
        "up",
        help="generate deploy/.env and start the pinned Switch stack",
        description=(
            "Create deploy/.env from .env.example with fresh random secrets if it is "
            "missing, start the pinned Switch 0.31.0 compose project, then wait for "
            "/health and for the setup container to exit 0. An existing deploy/.env "
            "is never overwritten."
        ),
    )
    down = commands.add_parser(
        "down",
        help="stop the stack (--wipe also removes volumes)",
        description=(
            "Stop the compose project 'splitbrain'. With --wipe also remove its Docker "
            "volumes and the local .splitbrain/ state; bootstrap is then needed again."
        ),
    )
    down.add_argument("--wipe", action="store_true", help="remove volumes and .splitbrain/")
    commands.add_parser(
        "status",
        help="show stack health, agents, rooms and the arbiter role",
        description=(
            "Print /health, the Switch version reported by the server, the Mattermost "
            "and Gateway URLs, the bootstrapped group, agents, rooms, GitHub reference "
            "and which agent currently holds the exclusive arbiter role."
        ),
    )
    commands.add_parser(
        "bootstrap",
        help="register agents, people and rooms (idempotent)",
        description=(
            "Register the four agents, create the Mattermost demo users, turn off agent "
            "greetings, open their addressing policies, provision the room group from "
            "the YAML template, attach the GitHub reference and print the demo logins. "
            "Running it twice changes nothing."
        ),
    )

    run = commands.add_parser(
        "run",
        help="run one agent in the foreground (or all of them)",
        description=(
            "Run one Splitbrain agent in the foreground with its own Switch connection. "
            "Use 'all' for the Sentinel, Arbiter, standby Arbiter and Verifier together."
        ),
    )
    run.add_argument(
        "agent",
        choices=["sentinel", "arbiter", "verifier", "arbiter-b", "all"],
        help="agent to run; 'all' starts the whole group",
    )
    run.add_argument("--tui", action="store_true", help="rich live view (Sentinel only)")

    seed_parser = commands.add_parser(
        "seed",
        help="post a demo scenario as its people",
        description=(
            "Post the messages of a scenario YAML as its people, with the configured "
            "delays. --auto-decide also answers consent and posts the decision and "
            "confirmation in the conflict room."
        ),
    )
    seed_parser.add_argument(
        "scenario",
        help=(
            "name of a YAML in seed/scenarios/: sso, sso-followup, refunds, hackathon, near-misses"
        ),
    )
    seed_parser.add_argument(
        "--auto-decide",
        action="store_true",
        help="answer consent and close the decision without a person",
    )

    demo_parser = commands.add_parser(
        "demo",
        help="one command: clean stack + bootstrap + agents + seed",
        description=(
            "Start from a clean state, bootstrap, launch the four agents, seed a "
            "scenario and print a summary with the conflict room, the decision, the "
            "corrected threads and the Mattermost URLs and logins. Every degraded "
            "mode (LLM replay, fixture evidence) is announced."
        ),
    )
    demo_parser.add_argument(
        "--scenario",
        default="sso",
        choices=("sso", "refunds", "hackathon"),
        help="scenario to seed (default: sso)",
    )
    demo_parser.add_argument(
        "--auto-decide",
        action="store_true",
        help="close the full loop without a person in the loop",
    )
    demo_parser.add_argument(
        "--offline",
        action="store_true",
        help="force replay cassettes and fixture evidence (no LLM, no GitHub network)",
    )
    demo_parser.add_argument(
        "--keep",
        action="store_true",
        help="reuse the running stack; still reset .splitbrain/sentinel.db",
    )
    demo_parser.add_argument(
        "--followup",
        action="store_true",
        help="after the decision and corrections, seed sso-followup to show decision memory",
    )
    demo_parser.add_argument(
        "--recovery",
        action="store_true",
        help=(
            "demonstrate arbiter takeover, Sentinel restart and duplicate confirmation handling; "
            "requires --auto-decide and --scenario sso"
        ),
    )

    record_parser = commands.add_parser(
        "record",
        help="refresh eval + scenario cassettes in record mode",
        description=(
            "Re-run the eval dataset and the seed scenarios against a live model and "
            "write the semantic cassettes in cassettes/. Requires "
            "SPLITBRAIN_LLM_API_KEY in .env.local or the process environment."
        ),
    )
    record_parser.add_argument(
        "--missing",
        action="store_true",
        help="record only entries without a cassette file; never overwrite existing ones",
    )
    eval_parser = commands.add_parser(
        "eval",
        help="run the labeled eval dataset and write eval/results.md",
        description=(
            "Run the 44 labeled pairs in eval/dataset.jsonl through the same "
            "prefilter, extraction, matching and classification pipeline the Sentinel "
            "uses. Print precision, recall, F1 and the confusion matrix for "
            "'contradiction', list every error and write eval/results.md."
        ),
    )
    eval_parser.add_argument(
        "--mode",
        choices=["replay", "live", "record"],
        default=None,
        help=(
            "replay = committed cassettes, no network (default); live and record "
            "need an API key; falls back to SPLITBRAIN_LLM_MODE when set"
        ),
    )
    eval_parser.add_argument(
        "--dataset",
        default=None,
        metavar="PATH",
        help=(
            "run an alternative JSONL dataset (for example eval/dataset-v2.jsonl); "
            "results go to eval/results-<suffix>.md or eval/results-<suffix>-live.md. "
            "Without it the command uses eval/dataset.jsonl exactly as before"
        ),
    )
    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    # These two are Switch-free: they must work on a clean clone with no .env.
    if args.command == "eval":
        if args.dataset:
            await evaluation.run(args.mode, dataset=args.dataset)
        else:
            await evaluation.run(args.mode)
        return 0
    if args.command == "record":
        if args.missing:
            await recording.record_all(missing_only=True)
        else:
            await recording.record_all()
        return 0
    if args.command == "demo":
        demo.validate_options(
            scenario=args.scenario,
            auto_decide=args.auto_decide,
            followup=args.followup,
            recovery=args.recovery,
        )
        demo_kwargs: dict[str, Any] = {
            "scenario": args.scenario,
            "auto_decide": args.auto_decide,
            "offline": args.offline,
            "keep": args.keep,
        }
        if args.followup:
            demo_kwargs["followup"] = True
        if args.recovery:
            demo_kwargs["recovery"] = True
        await demo.run(**demo_kwargs)
        return 0

    settings = Settings.load(require_env_file=args.command != "up")
    if args.command == "up":
        await stack.up(settings)
    elif args.command == "down":
        await stack.down(settings, wipe=args.wipe)
    elif args.command == "status":
        await stack.status(settings)
        await bootstrap.print_status(settings)
    elif args.command == "bootstrap":
        await bootstrap.run(settings)
    elif args.command == "run":
        if args.agent == "sentinel":
            await sentinel_agent.run_forever(settings, tui=args.tui)
        elif args.agent == "arbiter":
            await arbiter_agent.run_forever(settings)
        elif args.agent == "arbiter-b":
            await arbiter_agent.run_forever(settings, name="splitbrain-arbiter-b")
        elif args.agent == "verifier":
            await verifier_agent.run_forever(settings)
        else:
            await demo.run_agents(settings)
    elif args.command == "seed":
        await seed.run(settings, args.scenario, auto_decide=args.auto_decide)
    else:
        raise SplitbrainError(f"Unknown command: {args.command}")
    return 0


def _utf8_console(streams: Sequence[Any] | None = None) -> None:
    """Windows redirected output defaults to a legacy codepage; keep UTF-8.

    With `splitbrain demo > log.txt`, an em dash in a banner used to arrive as a
    replacement character. `errors="replace"` keeps the stream writable even
    when a caller replaces stdout with something that cannot be reconfigured.
    """
    targets = streams if streams is not None else (sys.stdout, sys.stderr)
    for stream in targets:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_console()
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_dispatch(args))
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nsplitbrain: stopped.", file=sys.stderr)
        return 130
    except SplitbrainError as exc:
        print(f"splitbrain: {exc}", file=sys.stderr)
        return 1
