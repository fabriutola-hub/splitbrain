"""Shared agent runtime: stream loop, event queue, banner and graceful Ctrl+C.

`SwitchAgent.run` dispatches frames from inside the SSE read loop. The handler in
this module only puts the frame on an unbounded asyncio.Queue, so the read loop
never waits for a model call, a SQLite write or a Switch operation. A separate
worker task drains that queue and runs the agent-specific logic.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Sequence
from typing import Protocol

from ..config import LLMSettings
from ..switch.client import SwitchAgent
from ..switch.events import MessageFrame, SwitchFrame

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)-30s %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


class FrameProcessor(Protocol):
    """Agent-specific frame handling; always invoked from a worker task."""

    async def start(self) -> None: ...

    async def on_frame(self, frame: SwitchFrame) -> None: ...

    async def aclose(self) -> None: ...


def configure_logging(handler: logging.Handler | None = None) -> None:
    """Send all logs to stdout, or to the TUI's in-memory footer when --tui."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root.addHandler(handler)
    # One line per HTTP request would drown the stream events in the demo logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def print_banner(name: str, llm: LLMSettings) -> None:
    """State the model mode, model and base URL; never print the API key."""
    print(f"Splitbrain {name} starting up", flush=True)
    print(f"LLM: mode={llm.mode} | model={llm.model} | base_url={llm.base_url}", flush=True)
    if llm.mode == "replay":
        print("[DEGRADED] replay: recorded model responses only, no network calls.", flush=True)
    elif llm.mode == "record":
        print("LLM record mode: writing a cassette for each new message and pair.", flush=True)
    print("Silent by default: this agent never posts in team rooms.", flush=True)
    print("Press Ctrl+C to stop.", flush=True)


def print_service_banner(name: str, lines: Sequence[str]) -> None:
    """Banner for agents that do not call the model (Arbiter, Verifier)."""
    print(f"Splitbrain {name} starting up", flush=True)
    for line in lines:
        print(line, flush=True)
    print("Press Ctrl+C to stop.", flush=True)


def reply_thread(frame: MessageFrame) -> str:
    """Switch thread ids are the root message id; replies carry that in thread_id."""
    return frame.payload.thread_id or frame.payload.message_id


class AgentRuntime:
    """Owns one SwitchAgent stream, one frame queue and one frame worker."""

    def __init__(
        self,
        *,
        agent: SwitchAgent,
        processor: FrameProcessor,
        name: str,
        llm: LLMSettings | None = None,
        stop: asyncio.Event | None = None,
    ) -> None:
        self.agent = agent
        self.processor = processor
        self.name = name
        self.llm = llm
        self.stop = stop or asyncio.Event()
        self.frames: asyncio.Queue[SwitchFrame] = asyncio.Queue()

    async def _enqueue(self, frame: SwitchFrame) -> None:
        # Runs inside the SSE read loop: no awaits, no I/O, no unbounded blocking.
        self.frames.put_nowait(frame)

    async def _consume(self) -> None:
        while not self.stop.is_set():
            try:
                frame = await asyncio.wait_for(self.frames.get(), timeout=0.2)
            except TimeoutError:
                continue
            try:
                await self.processor.on_frame(frame)
            except Exception:
                # A single bad frame must not tear down the stream; log the traceback.
                logger.exception("Worker failed on a %s frame; event dropped", frame.kind)
            finally:
                self.frames.task_done()

    async def serve(self) -> None:
        """Run until Ctrl+C; always release every resource in the finally block."""
        await self.processor.start()
        consumer = asyncio.create_task(self._consume(), name=f"{self.name}-worker")
        stream = asyncio.create_task(
            self.agent.run(self._enqueue, stop=self.stop), name=f"{self.name}-stream"
        )
        try:
            await stream
        except KeyboardInterrupt:
            logger.info("Ctrl+C received; stopping %s", self.name)
        finally:
            self.stop.set()
            stream.cancel()
            consumer.cancel()
            await asyncio.gather(stream, consumer, return_exceptions=True)
            try:
                await self.processor.aclose()
            finally:
                await self.agent.aclose()
