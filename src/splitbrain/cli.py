"""The only entry point: `uv run splitbrain <command>`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from . import bootstrap, evaluation, seed, stack
from .agents import sentinel as sentinel_agent
from .config import Settings, SplitbrainError

# Commands that belong to later milestones; they must exist in --help now.
_STUB_MILESTONES: dict[str, str] = {
    "demo": "M7",
    "record": "M7",
}


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

    run = commands.add_parser("run", help="run one agent in the foreground (M4)")
    run.add_argument("agent", choices=["sentinel", "arbiter", "verifier", "arbiter-b", "all"])
    run.add_argument("--tui", action="store_true", help="rich live view (Sentinel)")

    seed = commands.add_parser("seed", help="post a demo scenario (M4)")
    seed.add_argument("scenario", help="scenario name")
    seed.add_argument("--auto-decide", action="store_true", help="also post the decision")

    demo = commands.add_parser("demo", help="up + bootstrap + run all + seed (M7)")
    demo.add_argument("--scenario", default="sso", help="scenario name (default: sso)")
    demo.add_argument("--auto-decide", action="store_true", help="also post the decision")

    commands.add_parser("record", help="refresh the LLM cassettes (M7)")
    eval_parser = commands.add_parser("eval", help="run the labeled eval dataset (M3)")
    eval_parser.add_argument(
        "--mode",
        choices=["replay", "live", "record"],
        default=None,
        help="default: SPLITBRAIN_LLM_MODE, else offline replay",
    )
    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    milestone = _STUB_MILESTONES.get(args.command)
    if milestone:
        raise NotImplementedError(milestone)

    # M3 is Switch-free: eval must work on a clean clone without deploy/.env.
    if args.command == "eval":
        await evaluation.run(args.mode)
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
        if args.agent != "sentinel":
            raise SplitbrainError(
                f"Agent {args.agent!r} arrives in M5; M4 runs the Sentinel only "
                "('uv run splitbrain run sentinel [--tui]')."
            )
        await sentinel_agent.run_forever(settings, tui=args.tui)
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
