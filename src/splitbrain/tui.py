"""rich Live view for the demo video: 120 columns x 32 rows.

Left column: incoming messages per room, dimmed when the prefilter discards them.
Right column: extracted claims, plus the highlighted link between the two
assertions as soon as a candidate is sent to the Arbiter.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from dataclasses import dataclass

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import LLMSettings

WIDTH = 120
HEIGHT = 32
MAX_MESSAGES = 22
MAX_CLAIMS = 12
MAX_LOGS = 2
SIDE_HEIGHT = 24
LOG_HEIGHT = 5


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    room: str
    author: str
    text: str
    keep: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ClaimView:
    room: str
    author: str
    subject: str
    scope: str
    value: str
    key: str


@dataclass(frozen=True, slots=True)
class CandidateLink:
    candidate_id: str
    a: ClaimView
    b: ClaimView
    confidence: float
    reason: str


class _TuiLogHandler(logging.Handler):
    """Keep log lines in the footer instead of corrupting the live display."""

    def __init__(self, view: SentinelTui) -> None:
        super().__init__(level=logging.INFO)
        self._view = view

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._view.add_log(self.format(record))
        except Exception:
            self.handleError(record)


class SentinelTui:
    def __init__(self, llm: LLMSettings | None = None) -> None:
        self.llm = llm
        self.messages: deque[IncomingMessage] = deque(maxlen=MAX_MESSAGES)
        self.claims: deque[ClaimView] = deque(maxlen=MAX_CLAIMS)
        self.logs: deque[str] = deque(maxlen=MAX_LOGS)
        self.link: CandidateLink | None = None
        self.candidates = 0
        self.filtered = 0
        self._lock = threading.Lock()
        # Windows Terminal renders the full 120x32; rich's legacy-Windows mode
        # would reserve one column and wrap every second line. Some shells set
        # TERM=dumb, which makes rich skip every Live refresh: --tui explicitly
        # asked for a live view, so give the Console a terminal-capable TERM.
        console_env = dict(os.environ)
        if console_env.get("TERM", "").lower() in {"", "dumb", "unknown"}:
            console_env["TERM"] = "xterm-256color"
        self._console = Console(
            width=WIDTH,
            height=HEIGHT,
            force_terminal=True,
            color_system="standard",
            legacy_windows=False,
            _environ=console_env,
        )
        self._live: Live | None = None
        self._log_handler: logging.Handler = _TuiLogHandler(self)

    def log_handler(self) -> logging.Handler:
        return self._log_handler

    def start(self) -> None:
        self._live = Live(
            get_renderable=self.render,
            console=self._console,
            refresh_per_second=4,
            screen=False,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def add_message(self, room: str, author: str, text: str, keep: bool, reason: str) -> None:
        with self._lock:
            self.messages.append(IncomingMessage(room, author, text, keep, reason))
            if not keep:
                self.filtered += 1

    def add_claim(self, claim: ClaimView) -> None:
        with self._lock:
            self.claims.append(claim)

    def add_candidate(self, link: CandidateLink) -> None:
        with self._lock:
            self.link = link
            self.candidates += 1

    def add_log(self, line: str) -> None:
        with self._lock:
            self.logs.append(_one_line(line))

    def render(self) -> RenderableType:
        # Live refreshes from its own thread: snapshot everything under the lock.
        with self._lock:
            messages = list(self.messages)[-SIDE_HEIGHT:]
            claims = list(self.claims)
            logs = list(self.logs)
            link = self.link
            candidates = self.candidates
            filtered = self.filtered

        mode = self.llm.mode if self.llm is not None else "?"
        model = _clip(self.llm.model, 24) if self.llm is not None else "?"
        header = Text(
            f" SPLITBRAIN SENTINEL   LLM {mode} | {model}   "
            f"messages {len(messages)} | filtered {filtered} | candidates {candidates}",
            style="bold white on blue",
        )

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(self._left(messages), self._right(claims, link))
        return Group(header, grid, self._log_panel(logs))

    @staticmethod
    def _left(messages: list[IncomingMessage]) -> Panel:
        body = Text()
        if not messages:
            body.append("Waiting for messages...\n", style="dim")
        for item in messages:
            marker = ">>" if item.keep else ".."
            line = (
                f"{marker} #{_clip(item.room, 11):<11} {_clip(item.author, 7):<7} "
                f"{_clip(_one_line(item.text), 26)}"
            )
            if not item.keep:
                body.append(line + "\n", style="dim")
            else:
                body.append(line + "\n")
        return Panel(
            body,
            title="INCOMING MESSAGES  (dim = prefilter discard)",
            border_style="blue",
            height=SIDE_HEIGHT,
            padding=(0, 1),
        )

    @staticmethod
    def _right(claims: list[ClaimView], link: CandidateLink | None) -> Panel:
        body = Text()
        if link is not None:
            body.append(
                f"  CANDIDATE {link.candidate_id}  confidence {link.confidence:.2f}\n",
                style="bold black on bright_yellow",
            )
            body.append(
                f"  #{link.a.room} {link.a.author}: {_clip(_one_line(link.a.value), 40)}\n",
                style="bold red",
            )
            body.append("            |  CONTRADICTION  |\n", style="bold red")
            body.append(
                f"  #{link.b.room} {link.b.author}: {_clip(_one_line(link.b.value), 40)}\n",
                style="bold red",
            )
            body.append(f"  {_clip(_one_line(link.reason), 48)}\n", style="bold yellow")
            body.append("  sent to arbiter in splitbrain-ops\n\n", style="bold green")

        body.append("EXTRACTED CLAIMS\n", style="bold cyan")
        shown = claims[-10:]
        if not shown:
            body.append("  none yet\n", style="dim")
        for claim in shown:
            body.append(
                f"  #{_clip(claim.room, 9):<9} {_clip(claim.subject, 12):<12} "
                f"{_clip(claim.scope, 6):<6} {_clip(claim.value, 16)}\n",
                style="cyan",
            )
        return Panel(
            body,
            title="CLAIMS + CANDIDATE LINK",
            border_style="yellow",
            height=SIDE_HEIGHT,
            padding=(0, 1),
        )

    @staticmethod
    def _log_panel(logs: list[str]) -> Panel:
        body = Text()
        for line in logs:
            body.append(_clip(line, 108) + "\n", style="dim")
        if not logs:
            body.append("ready\n", style="dim")
        return Panel(body, title="LOG", border_style="grey50", height=LOG_HEIGHT, padding=(0, 1))
