"""M0 tests: stack orchestration without touching real Docker containers."""

from __future__ import annotations

from pathlib import Path

import pytest

from splitbrain import stack
from splitbrain.config import Paths, Settings


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    (deploy / ".env.example").write_bytes(Paths.default().env_example.read_bytes())
    (deploy / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    fake_docker = tmp_path / "docker.exe"
    fake_docker.touch()
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_DOCKER", str(fake_docker))
    return Settings.load(require_env_file=False)


@pytest.fixture
def fake_docker(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    async def run(args: list[str], settings: Settings) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(stack, "_docker", run)
    return calls


@pytest.mark.parametrize("wipe", [False, True])
async def test_down_builds_the_expected_compose_command(
    settings: Settings, fake_docker: list[list[str]], wipe: bool
) -> None:
    await stack.down(settings, wipe=wipe)
    assert len(fake_docker) == 1
    args = fake_docker[0]
    if wipe:
        assert args[-2:] == ["down", "--volumes"]
    else:
        assert args[-1] == "down"
        assert "--volumes" not in args
    assert "-p" in args and "splitbrain" in args


async def test_up_waits_for_health_and_setup(
    settings: Settings,
    fake_docker: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    waited: list[str] = []

    async def wait_health(current: Settings) -> None:
        waited.append("health")

    async def wait_setup(current: Settings) -> None:
        waited.append("setup")

    monkeypatch.setattr(stack, "_wait_for_health", wait_health)
    monkeypatch.setattr(stack, "_wait_for_setup", wait_setup)

    await stack.up(settings)

    assert waited == ["health", "setup"]
    assert fake_docker[0][-2:] == ["up", "-d"]
    output = capsys.readouterr().out
    assert "Created deploy/.env with fresh random secrets." in output
    assert "Splitbrain stack is up (Switch 0.31.0)." in output
