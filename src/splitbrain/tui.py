"""rich Live view for the demo video: readable at 120x32 and 100x30.

Left column: messages from people in team rooms, with full room and author
names and the message wrapped over two lines. Right column: the lifecycle of the
current candidate, one step per line as the Sentinel sees packets in ops.
Internal traffic (ops rooms, conflict rooms, agents, platform messages) is
never shown as a person's message; the header counts it instead.

One outer Panel holds both columns and a single vertical divider, so there is
no doubled border and no column can outgrow the console width.
"""

from __future__ import annotations

import logging
import os
import textwrap
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from rich.cells import cell_len
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .bootstrap import DEMO_USER_DISPLAY_NAMES
from .config import LLMSettings

WIDTH = 120
HEIGHT = 32
LOG_HEIGHT = 5
MAX_MESSAGES = 8
MAX_LOGS = 3
MAX_STEP_LINES = 2

# The TUI footer shows events a viewer can follow, not transport housekeeping.
MEANINGFUL_LOGS: tuple[str, ...] = (
    "Extracted ",
    "No alert:",
    "CANDIDATE ",
    "Consent ",
    "Asked @",
    "Corrections posted",
    "Decision recorded",
    "Consent answer",
)


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _fit(text: str, width: int) -> str:
    """Clip by display cells, so accented names and emoji cannot overflow."""
    if cell_len(text) <= width:
        return text
    out = ""
    for char in text:
        if cell_len(out + char) > width - 1:
            break
        out += char
    return out + "…"


def _wrap(text: str, width: int, limit: int) -> list[str]:
    lines = textwrap.wrap(
        _one_line(text), width=width, break_long_words=False, break_on_hyphens=False
    ) or [""]
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = _fit(f"{lines[-1]} …", width)
    return lines


def _clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def _display_name(author: str) -> str:
    name = DEMO_USER_DISPLAY_NAMES.get(author)
    return f"{name} (@{author})" if name else author


def _first_name(author: str) -> str:
    return _display_name(author).split()[0]


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    room: str
    author: str
    text: str
    keep: bool
    reason: str
    at: str = ""


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


@dataclass(frozen=True, slots=True)
class LifecycleStep:
    at: str
    text: str


class _TuiLogHandler(logging.Handler):
    """Keep only meaningful events in the footer, never transport noise."""

    def __init__(self, view: SentinelTui) -> None:
        super().__init__(level=logging.INFO)
        self._view = view

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if not any(marker in message for marker in MEANINGFUL_LOGS):
            return
        try:
            self._view.add_log(self.format(record))
        except Exception:
            self.handleError(record)


class SentinelTui:
    def __init__(
        self,
        llm: LLMSettings | None = None,
        *,
        width: int = WIDTH,
        height: int = HEIGHT,
    ) -> None:
        self.llm = llm
        self.width = width
        self.height = height
        self.body_height = height - LOG_HEIGHT - 1
        self.messages: deque[IncomingMessage] = deque(maxlen=MAX_MESSAGES)
        self.claims: deque[ClaimView] = deque(maxlen=12)
        self.logs: deque[str] = deque(maxlen=MAX_LOGS)
        self.link: CandidateLink | None = None
        self.steps: dict[str, list[LifecycleStep]] = {}
        self._step_keys: dict[str, set[str]] = {}
        self.active_candidate = ""
        self.candidates = 0
        self.filtered = 0
        self.internal = 0
        self._lock = threading.Lock()
        # Windows Terminal renders the full width; rich's legacy-Windows mode
        # would reserve one column and wrap every second line. Some shells set
        # TERM=dumb, which makes rich skip every Live refresh: --tui explicitly
        # asked for a live view, so give the Console a terminal-capable TERM.
        console_env = dict(os.environ)
        if console_env.get("TERM", "").lower() in {"", "dumb", "unknown"}:
            console_env["TERM"] = "xterm-256color"
        self._console = Console(
            width=width,
            height=height,
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

    def add_message(
        self,
        room: str,
        author: str,
        text: str,
        keep: bool,
        reason: str,
        *,
        at: str | None = None,
    ) -> None:
        with self._lock:
            self.messages.append(
                IncomingMessage(room, author, text, keep, reason, at or _clock()[:5])
            )
            if not keep:
                self.filtered += 1

    def add_internal(self) -> None:
        with self._lock:
            self.internal += 1

    def add_claim(self, claim: ClaimView) -> None:
        with self._lock:
            self.claims.append(claim)

    def add_candidate(self, link: CandidateLink) -> None:
        with self._lock:
            self.link = link
            self.candidates += 1
            self.active_candidate = link.candidate_id

    def add_step(self, candidate_id: str, key: str, text: str, *, at: str | None = None) -> None:
        with self._lock:
            steps = self.steps.setdefault(candidate_id, [])
            keys = self._step_keys.setdefault(candidate_id, set())
            if key in keys:
                return
            keys.add(key)
            steps.append(LifecycleStep(at or _clock(), text))
            if not self.active_candidate:
                self.active_candidate = candidate_id

    def add_log(self, line: str) -> None:
        with self._lock:
            self.logs.append(_one_line(line))

    def render(self) -> RenderableType:
        with self._lock:
            messages = list(self.messages)
            steps = list(self.steps.get(self.active_candidate, []))
            logs = list(self.logs)
            candidate_id = self.active_candidate
            link = self.link
            internal = self.internal
            filtered = self.filtered
            candidates = self.candidates

        # Panel reserves two border cells, two padding cells and one cell for
        # the title layout; content wider than this is folded onto a new line.
        inner = self.width - 5
        left_w = int(inner * 0.54)
        right_w = inner - left_w - 3  # " │ " separator
        data_rows = max(self.body_height - 4, 1)
        left = self._left_lines(messages, left_w, data_rows)
        right = self._right_lines(candidate_id, steps, link, right_w, data_rows)

        rows: list[tuple[str, str, str, str, str]] = [
            ("INCOMING MESSAGES", "bold cyan", "CANDIDATE LIFECYCLE", "bold yellow", " │ "),
            ("─" * left_w, "dim", "─" * right_w, "dim", "─┼─"),
        ]
        for index in range(data_rows):
            left_text, left_style = left[index]
            right_text, right_style = right[index]
            rows.append((left_text, left_style or "", right_text, right_style or "", " │ "))
        body = Text()
        for index, (left_text, left_style, right_text, right_style, sep) in enumerate(rows):
            if index:
                body.append("\n")
            self._row(
                body,
                left_text,
                left_style,
                right_text,
                right_style,
                left_w,
                right_w,
                sep=sep,
            )
        main = Panel(
            body,
            title="SPLITBRAIN SENTINEL",
            border_style="blue",
            width=self.width,
            height=self.body_height,
            padding=(0, 1),
        )
        header = Text(
            _fit(self._header(len(messages), internal, filtered, candidates), self.width).ljust(
                self.width
            ),
            style="bold white on blue",
        )
        log_lines = [_fit(line, inner) for line in logs[-MAX_LOGS:]]
        while len(log_lines) < MAX_LOGS:
            log_lines.insert(0, "")
        log = Panel(
            Text("\n".join(log_lines)),
            title="LOG",
            border_style="grey50",
            width=self.width,
            height=LOG_HEIGHT,
            padding=(0, 1),
        )
        return Group(header, main, log)

    def _header(self, messages: int, internal: int, filtered: int, candidates: int) -> str:
        mode = self.llm.mode if self.llm is not None else "?"
        model = self.llm.model if self.llm is not None else "?"
        short_model = model.rsplit("/", 1)[-1]

        def build(name: str, with_messages: bool, with_filtered: bool) -> str:
            parts = ["SPLITBRAIN SENTINEL", f"LLM {mode}", name, f"internal {internal}"]
            if with_messages:
                parts.append(f"messages {messages}")
            if with_filtered:
                parts.append(f"filtered {filtered}")
            parts.append(f"candidates {candidates}")
            return " " + " | ".join(parts)

        # Drop the organisation prefix first, then the least useful counters.
        for name, with_messages, with_filtered in (
            (model, True, True),
            (short_model, True, True),
            (short_model, True, False),
            (short_model, False, False),
        ):
            text = build(name, with_messages, with_filtered)
            if len(text) <= self.width:
                return text
        return text

    @staticmethod
    def _pad(text: str, width: int) -> str:
        fitted = _fit(text, width)
        return fitted + " " * max(0, width - cell_len(fitted))

    @classmethod
    def _row(
        cls,
        body: Text,
        left: str,
        left_style: str,
        right: str,
        right_style: str,
        left_w: int,
        right_w: int,
        *,
        sep: str = " │ ",
    ) -> None:
        """One row of exactly `width - 4` cells, with a single divider."""
        body.append(cls._pad(left, left_w), style=left_style)
        body.append(sep, style="dim")
        body.append(cls._pad(right, right_w), style=right_style)

    @staticmethod
    def _left_lines(
        messages: list[IncomingMessage], width: int, rows: int
    ) -> list[tuple[str, str | None]]:
        lines: list[tuple[str, str | None]] = []
        for item in messages:
            if len(lines) >= rows:
                break
            head = f"{item.at}  #{item.room} · {_display_name(item.author)}"
            line_style = None if item.keep else "dim"
            lines.append((_fit(head, width), line_style))
            for wrapped in _wrap(item.text, width - 2, MAX_STEP_LINES):
                if len(lines) >= rows:
                    break
                lines.append((_fit(f"  {wrapped}", width), line_style))
        while len(lines) < rows:
            lines.append(("", None))
        return lines[:rows]

    @staticmethod
    def _pair_lines(link: CandidateLink | None) -> list[tuple[str, str | None]]:
        """The two assertions the Sentinel linked, in three lines."""
        if link is None:
            return []

        def side(claim: ClaimView) -> str:
            scope = f" for {claim.scope}" if claim.scope and claim.scope != "*" else ""
            return (
                f"#{claim.room} {_first_name(claim.author)}: {claim.subject}{scope} = {claim.value}"
            )

        return [
            (side(link.a), "bold red"),
            ("⟷ CONTRADICTION ⟷", "bold red"),
            (side(link.b), "bold red"),
        ]

    @staticmethod
    def _right_lines(
        candidate_id: str,
        steps: list[LifecycleStep],
        link: CandidateLink | None,
        width: int,
        rows: int,
    ) -> list[tuple[str, str | None]]:
        lines: list[tuple[str, str | None]] = []
        if candidate_id:
            lines.append((_fit(f"[{candidate_id}]", width), "bold cyan"))
        lines.extend(SentinelTui._pair_lines(link))
        if not steps:
            lines.append(("  waiting for a candidate...", "dim"))
        for step in steps:
            if len(lines) >= rows:
                break
            wrapped = _wrap(f"✓ {step.text}", width - 10, MAX_STEP_LINES)
            lines.append((_fit(f"{step.at}  {wrapped[0]}", width), "bold green"))
            for continuation in wrapped[1:]:
                if len(lines) >= rows:
                    break
                lines.append((_fit(f"           {continuation}", width), "green"))
        while len(lines) < rows:
            lines.append(("", None))
        return lines[:rows]
