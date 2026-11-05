"""Generating deploy/.env from the committed example."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from dotenv import dotenv_values

from splitbrain.config import (
    PINNED_SWITCH_VERSION,
    SECRET_ENV_KEYS,
    Paths,
    SplitbrainError,
    ensure_env,
    read_env_values,
    redact,
)

EXAMPLE = Paths.default().env_example


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    example = deploy / ".env.example"
    example.write_bytes(EXAMPLE.read_bytes())
    return Paths(
        root=tmp_path,
        deploy_dir=deploy,
        env_file=deploy / ".env",
        env_example=example,
        compose_file=deploy / "docker-compose.yml",
        state_dir=tmp_path / ".splitbrain",
    )


def test_example_ships_no_secrets() -> None:
    values = dotenv_values(EXAMPLE)
    assert values["SWITCH_VERSION"] == PINNED_SWITCH_VERSION
    assert values["FRONTEND_BASE_URL"] == "http://localhost:3000"
    for key in SECRET_ENV_KEYS:
        assert values[key] == "", f"{key} must ship blank in the repo"


def test_ensure_env_fills_every_secret(paths: Paths) -> None:
    assert ensure_env(paths) is True
    content = paths.env_file.read_text(encoding="utf-8")
    assert "\r" not in content  # compose would otherwise interpolate a trailing \r
    values = dotenv_values(paths.env_file)

    assert values["SWITCH_VERSION"] == PINNED_SWITCH_VERSION
    assert values["FRONTEND_BASE_URL"] == "http://localhost:3000"
    for key in SECRET_ENV_KEYS:
        value = values[key] or ""
        assert value.strip(), f"{key} is blank in the generated .env"
        assert not re.search(r"\s", value), f"{key} contains whitespace"

    hex_values = [values[key] for key in SECRET_ENV_KEYS if key != "SECRET_KEYS"]
    assert all(re.fullmatch(r"[0-9a-f]{48}", value or "") for value in hex_values)
    assert re.fullmatch(r"local:[0-9a-f]{64}", values["SECRET_KEYS"] or "")
    assert len(set(hex_values + [values["SECRET_KEYS"]])) == len(SECRET_ENV_KEYS)

    # Every active assignment for a required secret must have a value.
    for line in content.splitlines():
        key = line.split("=", 1)[0]
        if key in SECRET_ENV_KEYS:
            assert line.split("=", 1)[1].strip(), f"blank secret line: {key}"


def test_ensure_env_keeps_existing_env(paths: Paths) -> None:
    assert ensure_env(paths) is True
    before = paths.env_file.read_bytes()
    assert ensure_env(paths) is False
    assert paths.env_file.read_bytes() == before
    assert read_env_values(paths)["DB_PASSWORD"] == (dotenv_values(paths.env_file)["DB_PASSWORD"])


def test_postgres_host_port_default_avoids_local_postgres(paths: Paths) -> None:
    """A clean clone must not publish Postgres on 5432, common on Windows."""
    assert dotenv_values(EXAMPLE)["POSTGRES_HOST_PORT"] == "55432"
    assert ensure_env(paths) is True
    assert dotenv_values(paths.env_file)["POSTGRES_HOST_PORT"] == "55432"
    assert read_env_values(paths)["POSTGRES_HOST_PORT"] == "55432"


def test_ensure_env_fails_loud_on_incomplete_example(paths: Paths) -> None:
    lines = [
        line
        for line in paths.env_example.read_text(encoding="utf-8").splitlines()
        if not line.startswith("SECRET_KEYS=")
    ]
    paths.env_example.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(SplitbrainError, match="SECRET_KEYS"):
        ensure_env(paths)
    assert not paths.env_file.exists()


def test_redact_scrubs_secrets() -> None:
    expected = "password=<redacted> and <redacted>"
    assert redact("password=abc123 and 1234", ["abc123", "1234"]) == expected
