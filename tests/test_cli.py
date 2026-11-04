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


def test_demo_dispatch_does_not_load_switch_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_run(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli.demo, "run", fake_run)
    monkeypatch.setattr(
        cli.Settings,
        "load",
        classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(AssertionError("no Switch here"))),
    )
    assert cli.main(["demo", "--scenario", "refunds", "--auto-decide", "--offline", "--keep"]) == 0
    assert calls == [
        {
            "scenario": "refunds",
            "auto_decide": True,
            "offline": True,
            "keep": True,
        }
    ]


def test_record_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    async def fake_record() -> None:
        calls.append(True)

    monkeypatch.setattr(cli.recording, "record_all", fake_record)
    monkeypatch.setattr(
        cli.Settings,
        "load",
        classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(AssertionError("no Switch here"))),
    )
    assert cli.main(["record"]) == 0
    assert calls == [True]


def test_run_sentinel_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, bool]] = []

    async def fake_run(settings: object, *, tui: bool) -> None:
        calls.append((settings, tui))

    monkeypatch.setattr(cli.sentinel_agent, "run_forever", fake_run)
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, **kwargs: "settings-object"))
    assert cli.main(["run", "sentinel", "--tui"]) == 0
    assert calls == [("settings-object", True)]


@pytest.mark.parametrize(
    ("argv", "module", "expected_kwargs"),
    [
        (["run", "arbiter"], "arbiter_agent", {}),
        (["run", "arbiter-b"], "arbiter_agent", {"name": "splitbrain-arbiter-b"}),
        (["run", "verifier"], "verifier_agent", {}),
    ],
)
def test_run_of_a_m5_agent_dispatches(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    module: str,
    expected_kwargs: dict[str, str],
) -> None:
    calls: list[tuple[object, dict[str, str]]] = []

    async def fake_run(settings: object, **kwargs: str) -> None:
        calls.append((settings, kwargs))

    monkeypatch.setattr(getattr(cli, module), "run_forever", fake_run)
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, **kwargs: "settings-object"))
    assert cli.main(argv) == 0
    assert calls == [("settings-object", expected_kwargs)]


def test_run_all_dispatches_to_the_agent_group(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    async def fake_run_agents(settings: object) -> None:
        calls.append(settings)

    monkeypatch.setattr(cli.demo, "run_agents", fake_run_agents)
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, **kwargs: "settings-object"))
    assert cli.main(["run", "all"]) == 0
    assert calls == ["settings-object"]


def test_keyboard_interrupt_exits_gracefully(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def interrupted(_args: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_dispatch", interrupted)
    assert cli.main(["run", "sentinel"]) == 130
    assert "stopped" in capsys.readouterr().err


def test_seed_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str, bool]] = []

    async def fake_seed(settings: object, name: str, *, auto_decide: bool) -> None:
        calls.append((settings, name, auto_decide))

    monkeypatch.setattr(cli.seed, "run", fake_seed)
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, **kwargs: "settings-object"))
    assert cli.main(["seed", "sso"]) == 0
    assert calls == [("settings-object", "sso", False)]


def test_eval_dispatch_does_not_load_switch_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    async def fake_run(mode: object) -> None:
        calls.append(mode)

    monkeypatch.setattr(cli.evaluation, "run", fake_run)
    monkeypatch.setattr(
        cli.Settings,
        "load",
        classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(AssertionError("no Switch here"))),
    )
    assert cli.main(["eval", "--mode", "replay"]) == 0
    assert calls == ["replay"]


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
