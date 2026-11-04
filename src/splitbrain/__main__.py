"""Allow `python -m splitbrain ...`; the demo uses it to spawn child agents."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
