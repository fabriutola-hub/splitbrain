"""Docker Compose stack control for the local Switch 0.31.0 stack."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import (
    COMPOSE_PROJECT,
    PINNED_SWITCH_VERSION,
    Settings,
    SplitbrainError,
    ensure_env,
    loopback_client,
    redact,
)

HEALTH_TIMEOUT_S = 180.0
SETUP_TIMEOUT_S = 240.0
POLL_INTERVAL_S = 2.0


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _run_sync(args: list[str]) -> CommandResult:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return CommandResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


async def _docker(args: list[str], settings: Settings) -> str:
    """Run one Docker command and fail loudly, with secrets scrubbed from the output."""
    result = await asyncio.to_thread(_run_sync, args)
    stdout = redact(result.stdout, settings.secret_values).strip()
    stderr = redact(result.stderr, settings.secret_values).strip()
    if result.returncode != 0:
        detail = "\n".join(part for part in (stdout, stderr) if part)
        raise SplitbrainError(
            f"{' '.join(args[:3])} failed with exit code {result.returncode}"
            + (f":\n{detail}" if detail else "")
        )
    return stdout


def _parse_health(response: httpx.Response, settings: Settings) -> dict[str, Any]:
    body = redact(response.text, settings.secret_values)
    if response.status_code != 200:
        raise SplitbrainError(f"GET /health returned {response.status_code}: {body}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SplitbrainError(f"GET /health returned a non-JSON body: {body}") from exc
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise SplitbrainError(f"GET /health returned an unexpected body: {body}")
    return payload


async def _wait_for_health(settings: Settings) -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    async with loopback_client() as client:
        while True:
            try:
                response = await client.get(settings.health_url, timeout=3.0)
            except httpx.TransportError:
                response = None
            if response is not None:
                _parse_health(response, settings)
                print(f"Switch healthy at {settings.health_url}")
                return
            if time.monotonic() >= deadline:
                raise SplitbrainError(
                    f"Switch did not become healthy within {HEALTH_TIMEOUT_S:.0f}s; "
                    "inspect the stack with 'docker compose -p splitbrain logs switch'."
                )
            await asyncio.sleep(POLL_INTERVAL_S)


async def _setup_state(settings: Settings) -> dict[str, Any] | None:
    container_ids = (
        await _docker(settings.compose_args + ["ps", "-a", "-q", "setup"], settings)
    ).split()
    if not container_ids:
        return None
    raw = await _docker(
        [settings.docker, "inspect", "--format", "{{json .State}}", container_ids[0]], settings
    )
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SplitbrainError(f"docker inspect returned invalid JSON: {raw}") from exc
    if not isinstance(state, dict):
        raise SplitbrainError(f"docker inspect returned an unexpected state: {raw}")
    return state


async def _wait_for_setup(settings: Settings) -> None:
    deadline = time.monotonic() + SETUP_TIMEOUT_S
    while True:
        state = await _setup_state(settings)
        if state is not None and state.get("Status") == "exited":
            exit_code = state.get("ExitCode")
            if exit_code == 0:
                print("Switch setup container finished with exit code 0")
                return
            raise SplitbrainError(f"Switch setup container exited with code {exit_code}")
        if time.monotonic() >= deadline:
            raise SplitbrainError(
                f"Switch setup container did not exit 0 within {SETUP_TIMEOUT_S:.0f}s."
            )
        await asyncio.sleep(POLL_INTERVAL_S)


async def up(settings: Settings) -> None:
    if ensure_env(settings.paths):
        print("Created deploy/.env with fresh random secrets.")
        settings = Settings.load()
    if not settings.paths.compose_file.is_file():
        raise SplitbrainError(f"Missing {settings.paths.compose_file}")

    print(f"Starting compose project {COMPOSE_PROJECT} (profiles collab, gateway)...")
    output = await _docker(settings.compose_args + ["up", "-d"], settings)
    if output:
        print(output)
    await _wait_for_health(settings)
    await _wait_for_setup(settings)
    print(f"Splitbrain stack is up (Switch {PINNED_SWITCH_VERSION}).")
    print(f"  Mattermost: {settings.mattermost_url}")
    print(f"  Gateway:    {settings.gateway_url}")
    print(f"  Switch API: {settings.api_base_url}")


async def down(settings: Settings, *, wipe: bool) -> None:
    args = settings.compose_args + ["down"]
    if wipe:
        args.append("--volumes")
    action = " and removing volumes..." if wipe else "..."
    print(f"Stopping compose project {COMPOSE_PROJECT}{action}")
    output = await _docker(args, settings)
    if output:
        print(output)
    if wipe and settings.paths.state_dir.is_dir():
        if settings.paths.state_dir.parent != settings.paths.root:
            raise SplitbrainError(
                f"Refusing to remove {settings.paths.state_dir}: outside the repo."
            )
        await asyncio.to_thread(shutil.rmtree, settings.paths.state_dir)
        print(f"Removed {settings.paths.state_dir}")
    print("Splitbrain stack is down.")


async def _server_version(
    client: httpx.AsyncClient, settings: Settings, health: dict[str, Any]
) -> str:
    from_health = health.get("version")
    if isinstance(from_health, str) and from_health:
        return from_health
    server = health.get("server")
    if isinstance(server, dict) and isinstance(server.get("version"), str):
        return server["version"]

    # 0.31.0's /health is deliberately just {"status": "ok"}; /version needs an
    # agent token and /gateway/version a session. The login response carries the
    # server's own declaration, so that is where M0 reads the real version.
    response = await client.post(
        f"{settings.api_base_url}/gateway/auth/login",
        json={
            "email": settings.gateway_admin_email,
            "password": settings.gateway_admin_password,
        },
        timeout=10.0,
    )
    body = redact(response.text, settings.secret_values)
    if response.status_code != 200:
        raise SplitbrainError(f"POST /gateway/auth/login returned {response.status_code}: {body}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SplitbrainError(f"POST /gateway/auth/login returned a non-JSON body: {body}") from exc
    server = payload.get("server") if isinstance(payload, dict) else None
    version = server.get("version") if isinstance(server, dict) else None
    if not isinstance(version, str) or not version:
        raise SplitbrainError(f"Switch did not report its version in the login response: {body}")
    return version


async def status(settings: Settings) -> None:
    async with loopback_client() as client:
        try:
            response = await client.get(settings.health_url, timeout=5.0)
        except httpx.TransportError as exc:
            raise SplitbrainError(
                f"Cannot reach {settings.health_url}: {exc}. Is the stack up? "
                "Run 'uv run splitbrain up'."
            ) from exc
        health = _parse_health(response, settings)
        version = await _server_version(client, settings, health)
    print("switch: ok")
    print(f"switch version: {version}")
    print(f"compose project: {COMPOSE_PROJECT}")
    print(f"Mattermost: {settings.mattermost_url}")
    print(f"Gateway: {settings.gateway_url}")
