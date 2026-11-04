"""Mattermost REST helpers for the local Switch stack (loopback only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ..config import loopback_client, redact

API = "/api/v4"


class MattermostError(RuntimeError):
    """A Mattermost call failed; carries the operation, status and redacted body."""

    def __init__(self, operation: str, status: int, body: str) -> None:
        self.operation = operation
        self.status = status
        self.body = body
        super().__init__(f"Mattermost {operation!r} failed with HTTP {status}: {body}")


class UserRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    username: str = ""


class Channel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    display_name: str = ""
    type: str = ""


class Post(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    message: str = ""
    root_id: str = ""
    create_at: int = 0


class Thread(BaseModel):
    model_config = ConfigDict(extra="allow")

    order: list[str] = Field(default_factory=list)
    posts: dict[str, Post] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MattermostUser:
    """A logged-in person; posts and reads threads through their own token."""

    base_url: str
    username: str
    team_id: str
    _client: httpx.AsyncClient
    _owns_client: bool = True

    @classmethod
    async def login(
        cls,
        base_url: str,
        username: str,
        password: str,
        team_name: str = "switch",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> MattermostUser:
        owns_client = client is None
        http = client or loopback_client(timeout=10.0)
        response = await http.post(
            f"{base_url.rstrip('/')}{API}/users/login",
            json={"login_id": username, "password": password},
        )
        if response.status_code != 200:
            if owns_client:
                await http.aclose()
            raise MattermostError(
                "users/login",
                response.status_code,
                redact(response.text, (password,)),
            )
        token = response.headers.get("Token")
        if not token:
            if owns_client:
                await http.aclose()
            raise MattermostError("users/login", response.status_code, "no Token header")
        http.headers["Authorization"] = f"Bearer {token}"
        team_response = await http.get(f"{base_url.rstrip('/')}{API}/teams/name/{team_name}")
        if team_response.status_code != 200:
            if owns_client:
                await http.aclose()
            raise MattermostError(
                "teams/name", team_response.status_code, redact(team_response.text, (token,))
            )
        team_id = str(team_response.json()["id"])
        return cls(
            base_url=base_url.rstrip("/"),
            username=username,
            team_id=team_id,
            _client=http,
            _owns_client=owns_client,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _check(self, operation: str, response: httpx.Response) -> None:
        if not 200 <= response.status_code < 300:
            raise MattermostError(
                operation,
                response.status_code,
                redact(response.text, (self._client.headers.get("Authorization", ""),)),
            )

    async def channels(self) -> list[Channel]:
        response = await self._client.get(
            f"{self.base_url}{API}/users/me/teams/{self.team_id}/channels"
        )
        self._check("users/me/teams/channels", response)
        return [Channel.model_validate(item) for item in response.json()]

    async def channel_for_room(self, room_name: str) -> str:
        for channel in await self.channels():
            # Switch appends a short suffix when the channel name already exists.
            if channel.name == room_name or channel.name.startswith(f"{room_name}-"):
                return channel.id
        raise MattermostError("channel lookup", 404, f"no channel for room {room_name!r}")

    async def post(self, channel_id: str, message: str, *, root_id: str | None = None) -> str:
        payload: dict[str, Any] = {"channel_id": channel_id, "message": message}
        if root_id:
            payload["root_id"] = root_id
        response = await self._client.post(f"{self.base_url}{API}/posts", json=payload)
        self._check("posts", response)
        return Post.model_validate(response.json()).id

    async def reply(self, channel_id: str, root_id: str, message: str) -> str:
        return await self.post(channel_id, message, root_id=root_id)

    async def thread(self, post_id: str) -> list[Post]:
        response = await self._client.get(f"{self.base_url}{API}/posts/{post_id}/thread")
        self._check("posts/thread", response)
        thread = Thread.model_validate(response.json())
        return [thread.posts[pid] for pid in thread.order if pid in thread.posts]


class MattermostAdmin:
    def __init__(
        self,
        base_url: str,
        admin_user: str,
        admin_password: str,
        team_name: str = "switch",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._admin_user = admin_user
        self._admin_password = admin_password
        self.team_name = team_name
        self._owns_client = client is None
        self._client = client or loopback_client(timeout=10.0)
        self._team_id: str | None = None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def login(self) -> None:
        response = await self._client.post(
            f"{self.base_url}{API}/users/login",
            json={"login_id": self._admin_user, "password": self._admin_password},
        )
        if response.status_code != 200:
            raise MattermostError(
                "users/login",
                response.status_code,
                redact(response.text, (self._admin_password,)),
            )
        token = response.headers.get("Token")
        if not token:
            raise MattermostError("users/login", response.status_code, "no Token header")
        self._client.headers["Authorization"] = f"Bearer {token}"

    async def set_password(self, user_id: str, password: str) -> None:
        """Set a user's password as admin; repairs a lost demo password in state."""
        response = await self._client.put(
            f"{self.base_url}{API}/users/{user_id}/password",
            json={"new_password": password},
        )
        if response.status_code not in (200, 201, 204):
            raise MattermostError(
                "users/password",
                response.status_code,
                redact(response.text, (password,)),
            )

    async def team_id(self) -> str:
        if self._team_id is None:
            response = await self._client.get(f"{self.base_url}{API}/teams/name/{self.team_name}")
            if response.status_code != 200:
                raise MattermostError("teams/name", response.status_code, redact(response.text, ()))
            self._team_id = str(response.json()["id"])
        return self._team_id

    async def ensure_user(self, username: str, password: str) -> MattermostUser:
        """Create the person if needed, put them in the team, then log in as them."""
        lookup = await self._client.get(f"{self.base_url}{API}/users/username/{username}")
        if lookup.status_code == 200:
            user = UserRecord.model_validate(lookup.json())
        elif lookup.status_code == 404:
            created = await self._client.post(
                f"{self.base_url}{API}/users",
                json={
                    "username": username,
                    "email": f"{username}@example.test",
                    "password": password,
                    "first_name": "Integration",
                    "last_name": "Probe",
                },
            )
            if created.status_code not in (200, 201):
                raise MattermostError(
                    "users",
                    created.status_code,
                    redact(created.text, (password,)),
                )
            user = UserRecord.model_validate(created.json())
        else:
            raise MattermostError(
                "users/username", lookup.status_code, redact(lookup.text, (password,))
            )

        team = await self.team_id()
        member = await self._client.post(
            f"{self.base_url}{API}/teams/{team}/members",
            json={"team_id": team, "user_id": user.id},
        )
        # 409 means the person is already in the team; that is the desired state.
        if member.status_code not in (200, 201, 409):
            raise MattermostError(
                "teams/members", member.status_code, redact(member.text, (password,))
            )
        try:
            return await MattermostUser.login(self.base_url, username, password, self.team_name)
        except MattermostError as exc:
            # A previous failed run may have created the user with a password
            # that never reached state.json. Repair it instead of duplicating.
            if exc.status != 401:
                raise
            await self.set_password(user.id, password)
            return await MattermostUser.login(self.base_url, username, password, self.team_name)
