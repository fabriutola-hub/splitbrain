"""LLM settings precedence, degraded modes and internet vs loopback clients."""

from __future__ import annotations

from pathlib import Path

import pytest

from splitbrain.config import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLMSettings,
    SplitbrainError,
    internet_client,
    loopback_client,
)


def _env_file(root: Path, content: str) -> None:
    (root / ".env.local").write_text(content, encoding="utf-8")


def test_defaults_when_nothing_is_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    for key in (
        "SPLITBRAIN_LLM_BASE_URL",
        "SPLITBRAIN_LLM_MODEL",
        "SPLITBRAIN_LLM_API_KEY",
        "SPLITBRAIN_LLM_REASONING_EFFORT",
        "SPLITBRAIN_LLM_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = LLMSettings.load()
    assert settings.base_url == DEFAULT_LLM_BASE_URL
    assert settings.model == DEFAULT_LLM_MODEL
    assert settings.mode == "replay"
    assert settings.reasoning_effort is None


def test_process_environment_beats_env_local(tmp_path: Path, monkeypatch) -> None:
    _env_file(
        tmp_path,
        "SPLITBRAIN_LLM_API_KEY=local-key\n"
        "SPLITBRAIN_LLM_BASE_URL=https://local.example/v1\n"
        "SPLITBRAIN_LLM_MODEL=local/model\n"
        "SPLITBRAIN_LLM_REASONING_EFFORT=none\n",
    )
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_MODEL", "process/model")
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "process-key")
    monkeypatch.delenv("SPLITBRAIN_LLM_MODE", raising=False)
    settings = LLMSettings.load(mode="record")
    assert settings.model == "process/model"
    assert settings.api_key == "process-key"
    assert settings.base_url == "https://local.example/v1"
    assert settings.reasoning_effort == "none"
    assert settings.mode == "record"
    assert settings.cassettes_dir == tmp_path / "cassettes"
    assert settings.eval_dir == tmp_path / "eval"


def test_live_and_record_require_a_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.delenv("SPLITBRAIN_LLM_API_KEY", raising=False)
    with pytest.raises(SplitbrainError, match="SPLITBRAIN_LLM_API_KEY is missing"):
        LLMSettings.load(mode="live")
    assert LLMSettings.load(mode="replay").api_key == ""


def test_env_mode_and_explicit_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "unit-test-key")
    monkeypatch.setenv("SPLITBRAIN_LLM_MODE", "record")
    assert LLMSettings.load().mode == "record"
    assert LLMSettings.load(mode="replay").mode == "replay"
    monkeypatch.setenv("SPLITBRAIN_LLM_MODE", "nonsense")
    with pytest.raises(SplitbrainError, match="SPLITBRAIN_LLM_MODE"):
        LLMSettings.load()


async def test_only_loopback_disables_trust_env() -> None:
    async with internet_client() as internet, loopback_client() as loopback:
        assert internet.trust_env is True
        assert loopback.trust_env is False
