"""Stack orchestration without touching real Docker containers."""

from __future__ import annotations

from pathlib import Path

import pytest

from splitbrain import stack
from splitbrain.config import Paths, Settings, ensure_env


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


async def test_up_respects_an_existing_postgres_host_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    (deploy / ".env.example").write_bytes(Paths.default().env_example.read_bytes())
    (deploy / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    fake_docker = tmp_path / "docker.exe"
    fake_docker.touch()
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLITBRAIN_DOCKER", str(fake_docker))

    paths = Paths.default()
    assert ensure_env(paths) is True
    generated = paths.env_file.read_text(encoding="utf-8")
    customized = generated.replace("POSTGRES_HOST_PORT=55432", "POSTGRES_HOST_PORT=55433")
    assert customized != generated
    paths.env_file.write_text(customized, encoding="utf-8", newline="\n")
    before = paths.env_file.read_bytes()

    settings = Settings.load(require_env_file=False)
    assert settings.values["POSTGRES_HOST_PORT"] == "55433"

    calls: list[list[str]] = []

    async def run(args: list[str], current: Settings) -> str:
        calls.append(args)
        return ""

    async def no_wait(current: Settings) -> None:
        return None

    monkeypatch.setattr(stack, "_docker", run)
    monkeypatch.setattr(stack, "_wait_for_health", no_wait)
    monkeypatch.setattr(stack, "_wait_for_setup", no_wait)
    await stack.up(settings)

    # `up` never regenerates a deploy/.env that is already there, and compose is
    # pointed at that file, so a port chosen by the operator stays in force.
    assert paths.env_file.read_bytes() == before
    assert settings.values["POSTGRES_HOST_PORT"] == "55433"
    assert calls[0][-2:] == ["up", "-d"]
    assert str(paths.env_file) in calls[0]
    assert "Created deploy/.env" not in capsys.readouterr().out


DOCKER_PORT_ERROR = (
    "Error response from daemon: ports are not available: exposing port TCP "
    "127.0.0.1:8065 -> 127.0.0.1:0: listen tcp4 127.0.0.1:8065: bind: An attempt was "
    "made to access a socket in a way forbidden by its access permissions."
)


def test_port_conflict_hint_names_the_setting_to_change() -> None:
    hint = stack.port_conflict_hint(
        DOCKER_PORT_ERROR, {"API_HOST_PORT": "8000", "MATTERMOST_HOST_PORT": "8065"}
    )
    assert "MATTERMOST_HOST_PORT" in hint
    assert "host port 8065" in hint
    assert "18065" in hint
    assert "Troubleshooting" in hint


def test_port_conflict_hint_falls_back_when_the_port_is_unknown() -> None:
    hint = stack.port_conflict_hint(DOCKER_PORT_ERROR, {})
    assert "the matching *_HOST_PORT setting" in hint


def test_port_conflict_hint_is_empty_for_other_errors() -> None:
    assert stack.port_conflict_hint("no such image: switch:0.31.0", {}) == ""


async def test_docker_failure_carries_the_port_hint(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(args: list[str]) -> stack.CommandResult:
        return stack.CommandResult(returncode=1, stdout="", stderr=DOCKER_PORT_ERROR)

    monkeypatch.setattr(stack, "_run_sync", failing)
    with pytest.raises(stack.SplitbrainError, match="MATTERMOST_HOST_PORT in deploy/.env"):
        await stack._docker(["docker", "compose", "-p", "up"], settings)
