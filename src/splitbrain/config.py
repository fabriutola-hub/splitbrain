"""Paths, environment loading and typed settings for the Splitbrain CLI."""

from __future__ import annotations

import os
import re
import secrets
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

PINNED_SWITCH_VERSION = "0.31.0"
COMPOSE_PROJECT = "splitbrain"
COMPOSE_PROFILES = ("collab", "gateway")

# The keys upstream's `just init-env` fills; nothing else in .env.example is a
# required secret (CONTROLLER_TOKEN_SECRET and JWT_SECRET_KEY are optional,
# FEATURE_FLAGS_ENABLED is a flag, and commented-out lines are examples).
SECRET_ENV_KEYS: tuple[str, ...] = (
    "DB_PASSWORD",
    "DB_OWNER_PASSWORD",
    "AGENT_REGISTRATION_TOKEN",
    "GATEWAY_ADMIN_PASSWORD",
    "MATTERMOST_ADMIN_PASSWORD",
    "MATTERMOST_USER_PASSWORD",
    "SECRET_KEYS",
)
REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "SWITCH_VERSION",
    "DB_USER",
    "DB_OWNER_USER",
    "DB_NAME",
    "GATEWAY_ADMIN_EMAIL",
    "FRONTEND_BASE_URL",
)


class SplitbrainError(RuntimeError):
    """A configuration or stack error that stops the CLI with a clear message."""


@dataclass(frozen=True, slots=True)
class Paths:
    root: Path
    deploy_dir: Path
    env_file: Path
    env_example: Path
    compose_file: Path
    state_dir: Path

    @classmethod
    def default(cls) -> Paths:
        override = os.environ.get("SPLITBRAIN_ROOT", "").strip()
        root = Path(override or Path(__file__).resolve().parents[2]).resolve()
        deploy = root / "deploy"
        return cls(
            root=root,
            deploy_dir=deploy,
            env_file=deploy / ".env",
            env_example=deploy / ".env.example",
            compose_file=deploy / "docker-compose.yml",
            state_dir=root / ".splitbrain",
        )


def read_env_values(paths: Paths) -> dict[str, str]:
    """Merge .env.example, .env and process overrides, in that precedence order."""
    merged: dict[str, str] = {}
    for source in (paths.env_example, paths.env_file):
        if not source.is_file():
            continue
        for key, value in dotenv_values(source).items():
            if value is not None:
                merged[key] = value
    for key in tuple(merged) + ("SPLITBRAIN_ROOT", "SPLITBRAIN_DOCKER"):
        if key in os.environ:
            merged[key] = os.environ[key]
    return merged


def find_docker(values: Mapping[str, str]) -> str:
    """Locate the Docker CLI; Docker Desktop is not always on PATH on Windows."""
    override = values.get("SPLITBRAIN_DOCKER", "").strip()
    if override:
        if Path(override).is_file():
            return override
        raise SplitbrainError(f"SPLITBRAIN_DOCKER points to a missing file: {override}")

    on_path = shutil.which("docker")
    if on_path:
        return on_path

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates = (
        Path(program_files) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        Path("D:/Docker/DockerDesktop/resources/bin/docker.exe"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise SplitbrainError(
        "Docker CLI not found. Install Docker Desktop or set SPLITBRAIN_DOCKER "
        "to the full path of the docker executable."
    )


@dataclass(frozen=True, slots=True)
class Settings:
    paths: Paths
    values: dict[str, str]
    docker: str

    @classmethod
    def load(cls, *, require_env_file: bool = True) -> Settings:
        paths = Paths.default()
        if require_env_file and not paths.env_file.is_file():
            raise SplitbrainError("deploy/.env is missing; run 'splitbrain up' first.")
        values = read_env_values(paths)

        missing = [key for key in REQUIRED_ENV_KEYS if not values.get(key, "").strip()]
        if missing:
            raise SplitbrainError(
                f"Missing required settings in deploy/.env.example: {', '.join(missing)}"
            )
        version = values["SWITCH_VERSION"].strip()
        if version != PINNED_SWITCH_VERSION:
            raise SplitbrainError(
                f"SWITCH_VERSION must be pinned to {PINNED_SWITCH_VERSION}, got {version!r}."
            )
        if require_env_file:
            blanks = [key for key in SECRET_ENV_KEYS if not values.get(key, "").strip()]
            if blanks:
                raise SplitbrainError(f"deploy/.env has blank secrets: {', '.join(blanks)}")
        return cls(paths=paths, values=values, docker=find_docker(values))

    @property
    def api_base_url(self) -> str:
        bind = self.values.get("SWITCH_BIND_ADDR", "127.0.0.1").strip() or "127.0.0.1"
        port = self.values.get("API_HOST_PORT", "8000").strip() or "8000"
        return f"http://{bind}:{port}"

    @property
    def health_url(self) -> str:
        return f"{self.api_base_url}/health"

    @property
    def mattermost_url(self) -> str:
        port = self.values.get("MATTERMOST_HOST_PORT", "8065").strip() or "8065"
        return f"http://localhost:{port}"

    @property
    def gateway_url(self) -> str:
        return self.values["FRONTEND_BASE_URL"].strip().rstrip("/")

    @property
    def gateway_admin_email(self) -> str:
        return self.values["GATEWAY_ADMIN_EMAIL"].strip()

    @property
    def gateway_admin_password(self) -> str:
        return self.values.get("GATEWAY_ADMIN_PASSWORD", "").strip()

    @property
    def secret_values(self) -> tuple[str, ...]:
        return tuple(
            value for key, value in self.values.items() if key in SECRET_ENV_KEYS and value.strip()
        )

    @property
    def compose_args(self) -> list[str]:
        args = [
            self.docker,
            "compose",
            "-p",
            COMPOSE_PROJECT,
            "-f",
            str(self.paths.compose_file),
            "--env-file",
            str(self.paths.env_file),
        ]
        for profile in COMPOSE_PROFILES:
            args.extend(["--profile", profile])
        return args


def _fill_secrets(example: str, generated: Mapping[str, str]) -> str:
    lines: list[str] = []
    filled: set[str] = set()
    assignment = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
    for line in example.splitlines():
        match = assignment.match(line)
        if match and match.group(1) in generated:
            key = match.group(1)
            lines.append(f"{key}={generated[key]}")
            filled.add(key)
        else:
            lines.append(line)
    missing = sorted(set(generated) - filled)
    if missing:
        raise SplitbrainError(f"deploy/.env.example is missing keys: {', '.join(missing)}")
    return "\n".join(lines) + "\n"


def ensure_env(paths: Paths) -> bool:
    """Create deploy/.env with fresh secrets when it is absent. Returns True if created."""
    if paths.env_file.is_file():
        return False
    if not paths.env_example.is_file():
        raise SplitbrainError(f"Missing {paths.env_example}")
    generated = {key: secrets.token_hex(24) for key in SECRET_ENV_KEYS if key != "SECRET_KEYS"}
    generated["SECRET_KEYS"] = f"local:{secrets.token_hex(32)}"
    content = _fill_secrets(paths.env_example.read_text(encoding="utf-8"), generated)
    # CRLF would leave a trailing \r inside compose's interpolated secret values.
    with paths.env_file.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    if os.name == "posix":
        paths.env_file.chmod(0o600)
    return True


def redact(text: str, secret_values: Iterable[str]) -> str:
    """Remove secret values from anything that could reach stdout or an exception."""
    for value in sorted({v for v in secret_values if v}, key=len, reverse=True):
        text = text.replace(value, "<redacted>")
    return text
