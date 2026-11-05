"""Shared runtime: the stream handler only enqueues; a worker does the work."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from splitbrain.agents.base import AgentRuntime
from splitbrain.config import LLMSettings
from splitbrain.switch.events import GenericFrame, SwitchFrame


class StubProcessor:
    def __init__(self, done: asyncio.Event, count: int) -> None:
        self.done = done
        self.count = count
        self.frames: list[SwitchFrame] = []
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def on_frame(self, frame: SwitchFrame) -> None:
        self.frames.append(frame)
        if len(self.frames) == self.count:
            self.done.set()

    async def aclose(self) -> None:
        self.closed = True


class StubAgent:
    def __init__(self, frames: list[SwitchFrame], done: asyncio.Event) -> None:
        self.frames = frames
        self.done = done
        self.closed = False

    async def run(self, handler: Any, *, stop: asyncio.Event | None = None) -> None:
        for frame in self.frames:
            await handler(frame)
        await asyncio.wait_for(self.done.wait(), timeout=3.0)
        if stop is not None:
            stop.set()

    async def aclose(self) -> None:
        self.closed = True


def _llm(monkeypatch: Any, tmp_path: Any) -> LLMSettings:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.delenv("SPLITBRAIN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    return LLMSettings.load(mode="replay")


async def test_frames_are_dispatched_to_the_worker_and_resources_closed(
    monkeypatch: Any, tmp_path: Any
) -> None:
    frames = [GenericFrame(kind="ping", data={"n": 1}), GenericFrame(kind="ping", data={"n": 2})]
    done = asyncio.Event()
    processor = StubProcessor(done, count=2)
    agent = StubAgent(frames, done)
    runtime = AgentRuntime(
        agent=agent,  # type: ignore[arg-type]
        processor=processor,
        name="test-agent",
        llm=_llm(monkeypatch, tmp_path),
    )
    await runtime.serve()
    assert processor.started is True
    assert len(processor.frames) == 2
    assert processor.closed is True
    assert agent.closed is True
    assert runtime.stop.is_set()


async def test_a_failing_frame_does_not_stop_the_worker(monkeypatch: Any, tmp_path: Any) -> None:
    done = asyncio.Event()

    class FailingProcessor(StubProcessor):
        async def on_frame(self, frame: SwitchFrame) -> None:
            if not self.frames:
                self.frames.append(frame)
                raise RuntimeError("boom")
            await super().on_frame(frame)

    processor = FailingProcessor(done, count=2)
    agent = StubAgent([GenericFrame(kind="a"), GenericFrame(kind="b")], done)
    runtime = AgentRuntime(
        agent=agent,  # type: ignore[arg-type]
        processor=processor,
        name="test-agent",
        llm=_llm(monkeypatch, tmp_path),
    )
    await runtime.serve()
    assert len(processor.frames) == 2


async def test_cancellation_still_closes_every_resource(monkeypatch: Any, tmp_path: Any) -> None:
    done = asyncio.Event()
    processor = StubProcessor(done, count=99)
    agent = StubAgent([GenericFrame(kind="ping")], done)

    async def never_returns(handler: Any, *, stop: asyncio.Event | None = None) -> None:
        await asyncio.sleep(60)

    agent.run = never_returns  # type: ignore[method-assign]
    runtime = AgentRuntime(
        agent=agent,  # type: ignore[arg-type]
        processor=processor,
        name="test-agent",
        llm=_llm(monkeypatch, tmp_path),
    )
    task = asyncio.create_task(runtime.serve())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert processor.closed is True
    assert agent.closed is True
    assert runtime.stop.is_set()


async def test_setting_stop_while_the_stream_is_idle_shuts_down(
    monkeypatch: Any, tmp_path: Any
) -> None:
    """An idle SSE loop only sees keepalives, so serve() must watch stop itself."""
    done = asyncio.Event()
    processor = StubProcessor(done, count=99)
    agent = StubAgent([], done)

    async def idle_forever(handler: Any, *, stop: asyncio.Event | None = None) -> None:
        await asyncio.sleep(60)

    agent.run = idle_forever  # type: ignore[method-assign]
    runtime = AgentRuntime(
        agent=agent,  # type: ignore[arg-type]
        processor=processor,
        name="test-agent",
        llm=_llm(monkeypatch, tmp_path),
    )
    task = asyncio.create_task(runtime.serve())
    await asyncio.sleep(0.05)
    runtime.stop.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert processor.closed is True
    assert agent.closed is True


def test_print_banner_states_mode_without_the_key(
    capsys: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    from splitbrain.agents.base import print_banner

    print_banner("splitbrain-sentinel", _llm(monkeypatch, tmp_path))
    output = capsys.readouterr().out
    assert "mode=replay" in output
    assert "DEGRADED" in output
    assert "base_url=" in output


def test_tui_log_handler_does_not_write_to_stdout() -> None:
    from splitbrain.tui import SentinelTui

    view = SentinelTui()
    handler = view.log_handler()
    record = logging.LogRecord(
        "x", logging.INFO, "f.py", 1, "Extracted 1 claim(s) from #sales", (), None
    )
    handler.handle(record)
    assert "Extracted 1 claim(s) from #sales" in " ".join(view.logs)
