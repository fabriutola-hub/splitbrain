"""Unit tests for M2 bootstrap: no stack, no network."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from splitbrain import bootstrap
from splitbrain.config import Paths, Settings, SplitbrainError
from splitbrain.switch.gateway import GatewayBridge

REAL_ROOT = Paths.default().root


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    (deploy / ".env.example").write_bytes((REAL_ROOT / "deploy" / ".env.example").read_bytes())
    for folder in ("agents", "templates"):
        (tmp_path / folder).mkdir()
        for source in (REAL_ROOT / folder).iterdir():
            (tmp_path / folder / source.name).write_bytes(source.read_bytes())
    paths = Paths(
        root=tmp_path,
        deploy_dir=deploy,
        env_file=deploy / ".env",
        env_example=deploy / ".env.example",
        compose_file=deploy / "docker-compose.yml",
        state_dir=tmp_path / ".splitbrain",
    )
    values = {
        "SWITCH_VERSION": "0.31.0",
        "FRONTEND_BASE_URL": "http://localhost:3000",
        "API_HOST_PORT": "8000",
        "SWITCH_BIND_ADDR": "127.0.0.1",
        "MATTERMOST_HOST_PORT": "8065",
        "MATTERMOST_ADMIN_USER": "admin",
        "MATTERMOST_ADMIN_PASSWORD": "admin-secret",
        "MATTERMOST_TEAM_NAME": "switch",
        "GATEWAY_ADMIN_EMAIL": "admin@switch.local",
        "GATEWAY_ADMIN_PASSWORD": "gateway-secret",
        "AGENT_REGISTRATION_TOKEN": "reg-token",
    }
    return Settings(paths=paths, values=values, docker="docker")


class FakeAgent:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def op(self, name: str, /, **args: Any) -> Any:
        self.calls.append((name, args))
        value = self.responses[name]
        return value(args) if callable(value) else value

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class FakeGateway:
    def __init__(self, greetings: bool = True) -> None:
        self.greetings = greetings
        self.set_greetings_calls: list[tuple[str, bool]] = []
        self.addressing_calls: list[str] = []

    async def login(self) -> None:
        return None

    async def bridges(self) -> list[GatewayBridge]:
        return [
            GatewayBridge(
                bridge_id="bridge-1",
                display_name="Mattermost",
                agent_greetings_enabled=self.greetings,
                is_default=True,
            )
        ]

    async def set_greetings(self, bridge_id: str, enabled: bool) -> None:
        self.set_greetings_calls.append((bridge_id, enabled))

    async def open_addressing(self, agent_id: str) -> None:
        self.addressing_calls.append(agent_id)


def group_result() -> dict[str, Any]:
    return {
        "group_id": "group-1",
        "group_name": "Acme",
        "errors": [],
        "rooms": [
            {"room_id": f"room-{name}", "room_name": name, "failed_attachments": []}
            for name in bootstrap.ALL_ROOMS
        ],
    }


def linked_rooms() -> list[dict[str, str]]:
    return [{"target_room_id": f"room-{name}", "label": "watches"} for name in bootstrap.TEAM_ROOMS]


def test_template_structure_and_role_inputs(settings: Settings) -> None:
    text = bootstrap.template_text(settings)
    document = yaml.safe_load(text)
    assert document["version"] == 1
    assert document["group"]["name"] == "Acme"
    assert len(document["rooms"]) == 5
    assert len(document["links"]) == 4
    assert all(link["from"] == "splitbrain-ops" for link in document["links"])
    assert all(link["label"] == "watches" for link in document["links"])

    by_name = {room["name"]: room for room in document["rooms"]}
    assert by_name["engineering"]["channel_type"] == "channel_private"
    assert by_name["engineering"]["users"] == ["tomas"]
    assert by_name["sales"]["users"] == ["maria", "lucia"]
    assert by_name["splitbrain-ops"]["roles"][0]["exclusive"] is True
    assert by_name["splitbrain-ops"]["docs"][0]["name"] == "How Splitbrain works"

    assert document["params"]["arbiter_instructions"]["multiline"] is True
    assert document["params"]["arbiter_instructions"]["required"] is True
    assert "{arbiter_instructions}" in text
    assert "{verifier_instructions}" in text

    # The server substitutes typed values after parsing the YAML, so the
    # instructions keep their newlines; bootstrap passes them as `inputs`.
    inputs = bootstrap.template_inputs(settings)
    assert set(inputs) == {"arbiter_instructions", "verifier_instructions"}
    assert inputs["arbiter_instructions"] == (REAL_ROOT / "agents" / "arbiter.md").read_text(
        encoding="utf-8"
    )
    assert inputs["verifier_instructions"] == (REAL_ROOT / "agents" / "verifier.md").read_text(
        encoding="utf-8"
    )
    assert bootstrap.expected_channel_types(settings)["engineering"] == "channel_private"


def test_state_roundtrip_and_summary_never_prints_api_keys(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    state = bootstrap.BootstrapState(
        agents={
            name: bootstrap.AgentState(agent_id=f"id-{name}", api_key="TOP-SECRET-KEY")
            for name in bootstrap.AGENT_NAMES
        },
        rooms={
            name: bootstrap.RoomState(
                room_id=f"room-{name}", channel_type="channel_public", group_name="Acme"
            )
            for name in bootstrap.ALL_ROOMS
        },
        group="Acme",
        mattermost=bootstrap.MattermostState(
            password="demo-password", users=list(bootstrap.DEMO_USERS)
        ),
        reference=bootstrap.ReferenceState(
            reference_id="ref-1", name="Acme roadmap", attached_room_id="room-splitbrain-ops"
        ),
    )
    bootstrap.save_state(settings, state)
    loaded = bootstrap.load_state(settings)
    assert loaded == state

    bootstrap.print_summary(state)
    output = capsys.readouterr().out
    assert "TOP-SECRET-KEY" not in output
    assert "demo-password" in output
    assert "maria" in output and "fabrizio" in output
    for name in bootstrap.AGENT_NAMES:
        assert name in output
    for name in bootstrap.ALL_ROOMS:
        assert name in output


def test_roadmap_repo_precedence(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPLITBRAIN_ROADMAP_REPO", raising=False)
    assert bootstrap.roadmap_repo(settings) == bootstrap.DEFAULT_ROADMAP_REPO

    (settings.paths.root / ".env.local").write_text(
        "SPLITBRAIN_ROADMAP_REPO=https://example.test/from-file\n", encoding="utf-8"
    )
    assert bootstrap.roadmap_repo(settings) == "https://example.test/from-file"

    monkeypatch.setenv("SPLITBRAIN_ROADMAP_REPO", "https://example.test/from-env")
    assert bootstrap.roadmap_repo(settings) == "https://example.test/from-env"


async def test_ensure_rooms_creates_once_and_is_idempotent(settings: Settings) -> None:
    responses: dict[str, Any] = {
        "list_all_rooms": [],
        "create_room_from_yaml": group_result(),
        "get_room_detail": lambda args: {
            "channel_type": "channel_private"
            if args["room_id"] == "room-engineering"
            else "channel_public",
            "group_name": "Acme",
            "agent_names": list(bootstrap.AGENT_NAMES),
        },
        "connect_to_room": {"linked_rooms": linked_rooms(), "references": []},
    }
    agent = FakeAgent(responses)
    state = bootstrap.BootstrapState()
    await bootstrap.ensure_rooms(agent, settings, state)
    assert agent.names().count("create_room_from_yaml") == 1
    assert agent.names().count("link_rooms") == 0  # template links sufficed
    assert len(state.rooms) == 5
    assert state.group == "Acme"
    create_args = dict(agent.calls)["create_room_from_yaml"]
    assert "version: 1" in create_args["yaml"]
    assert "# Arbiter" in create_args["inputs"]["arbiter_instructions"]

    # A second run sees the rooms and must not create or invite anything again.
    responses["list_all_rooms"] = [
        {"room_id": f"room-{name}", "name": name} for name in bootstrap.ALL_ROOMS
    ]
    second = FakeAgent(responses)
    await bootstrap.ensure_rooms(second, settings, state)
    assert "create_room_from_yaml" not in second.names()
    assert "invite_agent_to_room" not in second.names()
    assert "link_rooms" not in second.names()


async def test_ensure_rooms_fails_loud_on_partial_group(settings: Settings) -> None:
    agent = FakeAgent({"list_all_rooms": [{"room_id": "r1", "name": "sales"}]})
    with pytest.raises(SplitbrainError, match="Partial Acme group"):
        await bootstrap.ensure_rooms(agent, settings, bootstrap.BootstrapState())


async def test_ensure_rooms_reports_template_errors(settings: Settings) -> None:
    broken = group_result()
    broken["errors"] = [{"room_name": "sales", "error": "bridge refused"}]
    agent = FakeAgent(
        {
            "list_all_rooms": [],
            "create_room_from_yaml": broken,
        }
    )
    with pytest.raises(SplitbrainError, match="reported errors"):
        await bootstrap.ensure_rooms(agent, settings, bootstrap.BootstrapState())


async def test_ensure_reference_creates_attaches_and_reuses(settings: Settings) -> None:
    state = bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(room_id=f"room-{name}", channel_type="channel_public")
            for name in bootstrap.ALL_ROOMS
        }
    )
    created: dict[str, Any] = {"id": "ref-1", "name": "Acme roadmap"}
    responses: dict[str, Any] = {
        "list_reference_types": [{"type": "github"}, {"type": "jira"}],
        "list_all_references": [],
        "create_reference": created,
        "connect_to_room": {"references": []},
        "attach_reference_to_room": {"ok": True},
    }
    agent = FakeAgent(responses)
    await bootstrap.ensure_reference(agent, settings, state)
    assert agent.names().count("create_reference") == 1
    assert agent.names().count("attach_reference_to_room") == 1
    assert dict(agent.calls)["create_reference"]["value"] == {
        "urls": [bootstrap.DEFAULT_ROADMAP_REPO]
    }
    assert state.reference is not None and state.reference.reference_id == "ref-1"

    responses["list_all_references"] = [created]
    responses["connect_to_room"] = {"references": [{"id": "ref-1"}]}
    second = FakeAgent(responses)
    await bootstrap.ensure_reference(second, settings, state)
    assert "create_reference" not in second.names()
    assert "attach_reference_to_room" not in second.names()


async def test_ensure_reference_requires_github_type(settings: Settings) -> None:
    state = bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(room_id=f"room-{name}", channel_type="channel_public")
            for name in bootstrap.ALL_ROOMS
        }
    )
    agent = FakeAgent({"list_reference_types": [{"type": "jira"}]})
    with pytest.raises(SplitbrainError, match="github is not an available"):
        await bootstrap.ensure_reference(agent, settings, state)


async def test_ensure_gateway_is_idempotent(settings: Settings) -> None:
    state = bootstrap.BootstrapState(
        agents={
            name: bootstrap.AgentState(agent_id=f"id-{name}", api_key="secret")
            for name in bootstrap.AGENT_NAMES
        }
    )
    gateway = FakeGateway(greetings=True)
    await bootstrap.ensure_gateway(settings, state, gateway=gateway)  # type: ignore[arg-type]
    assert gateway.set_greetings_calls == [("bridge-1", False)]
    assert len(gateway.addressing_calls) == 4

    settled = FakeGateway(greetings=False)
    await bootstrap.ensure_gateway(settings, state, gateway=settled)  # type: ignore[arg-type]
    assert settled.set_greetings_calls == []
    assert settled.addressing_calls == []


def test_extract_values_handles_mixed_shapes() -> None:
    entries = [
        {"target_room_id": "r1"},
        {"id": "r2"},
        "r3",
        {"unknown": "x"},
    ]
    assert bootstrap._extract_values(entries, ("target_room_id", "id")) == {"r1", "r2", "r3"}
