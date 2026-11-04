"""Unit tests for the Mattermost helpers (no network: respx)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from splitbrain.switch.mattermost import MattermostAdmin, MattermostError, MattermostUser

BASE = "http://mm.test"
API = "/api/v4"
ADMIN = "admin"
ADMIN_PASSWORD = "admin-secret"
TEAM_ID = "team-1"
USER = "it-user-abc12345"
USER_PASSWORD = "user-secret"


def mock_common(username_status: int, member_status: int = 201) -> None:
    respx.post(f"{BASE}{API}/users/login").mock(
        side_effect=[
            httpx.Response(200, json={"id": "admin-id"}, headers={"Token": "admin-token"}),
            httpx.Response(200, json={"id": "user-id"}, headers={"Token": "user-token"}),
        ]
    )
    respx.get(f"{BASE}{API}/teams/name/switch").mock(
        return_value=httpx.Response(200, json={"id": TEAM_ID})
    )
    if username_status == 404:
        respx.get(f"{BASE}{API}/users/username/{USER}").mock(
            return_value=httpx.Response(404, json={"message": "not found"})
        )
        respx.post(f"{BASE}{API}/users").mock(
            return_value=httpx.Response(201, json={"id": "user-id", "username": USER})
        )
    else:
        respx.get(f"{BASE}{API}/users/username/{USER}").mock(
            return_value=httpx.Response(200, json={"id": "user-id", "username": USER})
        )
    respx.post(f"{BASE}{API}/teams/{TEAM_ID}/members").mock(
        return_value=httpx.Response(member_status, json={})
    )


@respx.mock
async def test_ensure_user_creates_and_adds_to_team() -> None:
    mock_common(404)
    admin = MattermostAdmin(BASE, ADMIN, ADMIN_PASSWORD)
    user = None
    try:
        await admin.login()
        user = await admin.ensure_user(USER, USER_PASSWORD)
        assert user.username == USER
        assert user.team_id == TEAM_ID
    finally:
        if user is not None:
            await user.aclose()
        await admin.aclose()
    created = [call for call in respx.calls if call.request.url.path.endswith("/users")]
    assert json.loads(created[0].request.content)["email"] == f"{USER}@example.test"


@respx.mock
async def test_ensure_user_accepts_existing_user_and_existing_member() -> None:
    mock_common(200, member_status=409)
    admin = MattermostAdmin(BASE, ADMIN, ADMIN_PASSWORD)
    user = None
    try:
        await admin.login()
        user = await admin.ensure_user(USER, USER_PASSWORD)
        assert user.team_id == TEAM_ID
    finally:
        if user is not None:
            await user.aclose()
        await admin.aclose()


@respx.mock
async def test_channel_lookup_handles_the_name_suffix() -> None:
    respx.post(f"{BASE}{API}/users/login").mock(
        return_value=httpx.Response(200, json={"id": "u"}, headers={"Token": "token"})
    )
    respx.get(f"{BASE}{API}/teams/name/switch").mock(
        return_value=httpx.Response(200, json={"id": TEAM_ID})
    )
    respx.get(f"{BASE}{API}/users/me/teams/{TEAM_ID}/channels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "c1", "name": "town-square", "display_name": "Town Square", "type": "O"},
                {
                    "id": "c2",
                    "name": "it-room-abc-4a491dca",
                    "display_name": "it-room",
                    "type": "O",
                },
            ],
        )
    )
    user = await MattermostUser.login(BASE, USER, USER_PASSWORD)
    try:
        assert await user.channel_for_room("it-room-abc") == "c2"
        with pytest.raises(MattermostError, match="no channel"):
            await user.channel_for_room("missing-room")
    finally:
        await user.aclose()


@respx.mock
async def test_post_reply_and_read_thread() -> None:
    respx.post(f"{BASE}{API}/users/login").mock(
        return_value=httpx.Response(200, json={"id": "u"}, headers={"Token": "token"})
    )
    respx.get(f"{BASE}{API}/teams/name/switch").mock(
        return_value=httpx.Response(200, json={"id": TEAM_ID})
    )
    posts = respx.post(f"{BASE}{API}/posts").mock(
        side_effect=[
            httpx.Response(201, json={"id": "p1", "message": "root", "root_id": ""}),
            httpx.Response(201, json={"id": "p2", "message": "reply", "root_id": "p1"}),
        ]
    )
    respx.get(f"{BASE}{API}/posts/p1/thread").mock(
        return_value=httpx.Response(
            200,
            json={
                "order": ["p1", "p2"],
                "posts": {
                    "p1": {"id": "p1", "message": "root", "root_id": "", "create_at": 1},
                    "p2": {"id": "p2", "message": "reply", "root_id": "p1", "create_at": 2},
                },
            },
        )
    )
    user = await MattermostUser.login(BASE, USER, USER_PASSWORD)
    try:
        root_id = await user.post("c1", "root")
        await user.reply("c1", root_id, "reply")
        assert json.loads(posts.calls[1].request.content) == {
            "channel_id": "c1",
            "message": "reply",
            "root_id": "p1",
        }
        assert [post.message for post in await user.thread(root_id)] == ["root", "reply"]
    finally:
        await user.aclose()


@respx.mock
async def test_login_error_redacts_the_password() -> None:
    respx.post(f"{BASE}{API}/users/login").mock(
        return_value=httpx.Response(401, text=f"bad password {USER_PASSWORD}")
    )
    with pytest.raises(MattermostError) as error:
        await MattermostUser.login(BASE, USER, USER_PASSWORD)
    assert error.value.status == 401
    assert USER_PASSWORD not in str(error.value)
