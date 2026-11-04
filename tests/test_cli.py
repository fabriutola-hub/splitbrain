"""M0 tests: CLI surface, milestone stubs and fail-loud settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from splitbrain import cli
from splitbrain.config import PINNED_SWITCH_VERSION, Paths, Settings, SplitbrainError

COMMANDS = ("up", "down", "status", "bootstrap", "run", "seed", "demo", "record", "eval")


def test_help_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    for command in COMMANDS:
        assert command in output


@pytest.mark.parametrize(
    ("argv", "milestone"),
    [
        (["eval"], "M3"),
        (["run", "sentinel"], "M4"),
        (["seed", "sso"], "M4"),
        (["demo"], "M7"),
        (["record"], "M7"),
    ],
)
def test_stubs_raise_not_implemented(argv: list[str], milestone: str) -> None:
    with pytest.raises(NotImplementedError) as error:
        cli.main(argv)
    assert str(error.value) == milestone


def test_bootstrap_dispatch_calls_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    async def fake_run(settings: object) -> None:
        calls.append(settings)

    monkeypatch.setattr(cli.bootstrap, "run", fake_run)
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, **kwargs: "settings-object"))
    assert cli.main(["bootstrap"]) == 0
    assert calls == ["settings-object"]


def test_status_dispatch_includes_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_health(settings: object) -> None:
        calls.append("health")

    async def fake_bootstrap_status(settings: object) -> None:
        calls.append("bootstrap")

    monkeypatch.setattr(cli.stack, "status", fake_health)
    monkeypatch.setattr(cli.bootstrap, "print_status", fake_bootstrap_status)
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, **kwargs: "settings-object"))
    assert cli.main(["status"]) == 0
    assert calls == ["health", "bootstrap"]


def test_settings_require_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    with pytest.raises(SplitbrainError, match="deploy/.env is missing"):
        Settings.load()


def test_settings_reject_a_floating_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    example = Paths.default().env_example.read_text(encoding="utf-8")
    (deploy / ".env.example").write_text(
        example.replace(f"SWITCH_VERSION={PINNED_SWITCH_VERSION}", "SWITCH_VERSION=latest"),
        encoding="utf-8",
    )
    (deploy / ".env").write_text("SWITCH_VERSION=latest\n", encoding="utf-8")
    monkeypatch.setenv("SPLITBRAIN_ROOT", str(tmp_path))
    with pytest.raises(SplitbrainError, match="must be pinned"):
        Settings.load()


def test_compose_args_use_the_pinned_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_docker = tmp_path / "docker.exe"
    fake_docker.touch()
    monkeypatch.setenv("SPLITBRAIN_DOCKER", str(fake_docker))
    settings = Settings.load(require_env_file=False)
    args = settings.compose_args
    assert args[0] == str(fake_docker)
    assert args[1:4] == ["compose", "-p", "splitbrain"]
    assert args.count("--profile") == 2
    assert "collab" in args and "gateway" in args
    assert str(settings.paths.env_file) in args
    assert str(settings.paths.compose_file) in args
    assert settings.health_url.endswith("/health")
