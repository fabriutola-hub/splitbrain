"""Unit tests for the Gateway admin client (no network: respx)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from splitbrain.switch.gateway import GatewayAdmin, GatewayError

BASE = "http://switch.test"
EMAIL = "admin@switch.local"
PASSWORD = "gateway-admin-secret"
BRIDGE_ID = "bridge-1"


@respx.mock
async def test_login_and_bridges_use_the_cookie_session() -> None:
    respx.post(f"{BASE}/gateway/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"id": "u1", "name": "Admin", "server": {"version": "0.31.0"}},
            headers={"set-cookie": "switch_auth=session-1; Path=/"},
        )
    )
    route = respx.get(f"{BASE}/gateway/collaborations").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "bridge_id": BRIDGE_ID,
                    "display_name": "Mattermost",
                    "agent_greetings_enabled": True,
                    "is_default": True,
                }
            ],
        )
    )
    async with GatewayAdmin(BASE, EMAIL, PASSWORD) as admin:
        bridges = await admin.bridges()
        await admin.bridges()
    assert len(bridges) == 1
    assert bridges[0].bridge_id == BRIDGE_ID
    assert bridges[0].agent_greetings_enabled is True
    assert route.calls[0].request.headers.get("cookie") == "switch_auth=session-1"
    # The second bridges() call must not re-authenticate.
    assert len(respx.calls) == 3


@respx.mock
async def test_bridges_accept_the_legacy_id_key() -> None:
    respx.post(f"{BASE}/gateway/auth/login").mock(
        return_value=httpx.Response(200, json={"id": "u1"})
    )
    respx.get(f"{BASE}/gateway/collaborations").mock(
        return_value=httpx.Response(200, json=[{"id": "legacy-1", "display_name": "MM"}])
    )
    async with GatewayAdmin(BASE, EMAIL, PASSWORD) as admin:
        bridges = await admin.bridges()
    assert bridges[0].bridge_id == "legacy-1"


@respx.mock
async def test_set_greetings_and_open_addressing_payloads() -> None:
    respx.post(f"{BASE}/gateway/auth/login").mock(
        return_value=httpx.Response(200, json={"id": "u1"})
    )
    patch = respx.patch(f"{BASE}/gateway/collaborations/{BRIDGE_ID}").mock(
        return_value=httpx.Response(200, json={"bridge_id": BRIDGE_ID})
    )
    put = respx.put(f"{BASE}/gateway/agents/agent-1/addressing-policy").mock(
        return_value=httpx.Response(200, json={"id": "agent-1"})
    )
    async with GatewayAdmin(BASE, EMAIL, PASSWORD) as admin:
        await admin.set_greetings(BRIDGE_ID, False)
        await admin.open_addressing("agent-1")
    assert json.loads(patch.calls[0].request.content) == {"agent_greetings_enabled": False}
    assert json.loads(put.calls[0].request.content) == {"policy": None}


@respx.mock
async def test_login_error_redacts_the_password() -> None:
    respx.post(f"{BASE}/gateway/auth/login").mock(
        return_value=httpx.Response(401, text=f"bad password {PASSWORD}")
    )
    admin = GatewayAdmin(BASE, EMAIL, PASSWORD)
    try:
        with pytest.raises(GatewayError) as error:
            await admin.bridges()
        assert error.value.status == 401
        assert PASSWORD not in str(error.value)
        assert "<redacted>" in str(error.value)
    finally:
        await admin.aclose()
