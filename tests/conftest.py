"""Shared fakes: no unit test is allowed to touch the network."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from splitbrain.config import LLMSettings
from splitbrain.llm.cassette import CassetteStore
from splitbrain.llm.client import LLMClient


class FakeTransport:
    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        if not self.replies:
            raise AssertionError("fake LLM ran out of prepared replies")
        return self.replies.pop(0)

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def llm_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def make(
        replies: list[dict[str, Any]], *, mode: str = "record"
    ) -> tuple[LLMClient, FakeTransport, CassetteStore, LLMSettings]:
        monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
        monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "unit-test-key")
        monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
        settings = LLMSettings.load(mode=mode)
        store = CassetteStore(tmp_path / "cassettes", model=settings.model, mode=mode)
        transport = FakeTransport(replies)
        return LLMClient(settings, store, transport=transport), transport, store, settings

    return make
