"""The only entry point: `uv run splitbrain <command>`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from . import bootstrap, demo, evaluation, recording, seed, stack
from .agents import arbiter as arbiter_agent
from .agents import sentinel as sentinel_agent
from .agents import verifier as verifier_agent
from .config import Settings, SplitbrainError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="splitbrain",
        description="Control the local Switch stack and the Splitbrain agents.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    commands.add_parser("up", help="generate deploy/.env and start the pinned Switch stack")
    down = commands.add_parser("down", help="stop the stack (--wipe also removes volumes)")
    down.add_argument("--wipe", action="store_true", help="remove volumes and .splitbrain/")
    commands.add_parser("status", help="show stack health, agents, rooms and the group")
    commands.add_parser("bootstrap", help="register agents, people and rooms (idempotent)")

    run = commands.add_parser("run", help="run one agent in the foreground")
    run.add_argument("agent", choices=["sentinel", "arbiter", "verifier", "arbiter-b", "all"])
    run.add_argument("--tui", action="store_true", help="rich live view (Sentinel)")

    seed_parser = commands.add_parser("seed", help="post a demo scenario")
    seed_parser.add_argument("scenario", help="scenario name")
    seed_parser.add_argument("--auto-decide", action="store_true", help="also post the decision")

    demo_parser = commands.add_parser("demo", help="clean up + bootstrap + agents + seed")
    demo_parser.add_argument(
        "--scenario",
        default="sso",
        choices=("sso", "refunds", "hackathon"),
        help="scenario name (default: sso)",
    )
    demo_parser.add_argument("--auto-decide", action="store_true", help="close the loop alone")
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

    commands.add_parser("record", help="refresh eval + scenario cassettes in record mode")
    eval_parser = commands.add_parser("eval", help="run the labeled eval dataset (M3)")
    eval_parser.add_argument(
        "--mode",
        choices=["replay", "live", "record"],
        default=None,
        help="default: SPLITBRAIN_LLM_MODE, else offline replay",
    )
    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    # These two are Switch-free: they must work on a clean clone with no .env.
    if args.command == "eval":
        await evaluation.run(args.mode)
        return 0
    if args.command == "record":
        await recording.record_all()
        return 0
    if args.command == "demo":
        await demo.run(
            scenario=args.scenario,
            auto_decide=args.auto_decide,
            offline=args.offline,
            keep=args.keep,
        )
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_dispatch(args))
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nsplitbrain: stopped.", file=sys.stderr)
        return 130
    except SplitbrainError as exc:
        print(f"splitbrain: {exc}", file=sys.stderr)
        return 1
