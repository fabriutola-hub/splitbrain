"""Gateway admin API client for the local Switch stack (loopback only)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..config import loopback_client, redact

logger = logging.getLogger(__name__)


class GatewayError(RuntimeError):
    """A gateway admin call failed; carries the operation, status and redacted body."""

    def __init__(self, operation: str, status: int, body: str) -> None:
        self.operation = operation
        self.status = status
        self.body = body
        super().__init__(f"Gateway {operation!r} failed with HTTP {status}: {body}")


class GatewayBridge(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # 0.31.0 answers with `bridge_id`; older notes mention `id`.
    bridge_id: str = Field(validation_alias=AliasChoices("bridge_id", "id"))
    display_name: str = ""
    agent_greetings_enabled: bool = True
    is_default: bool = False


class GatewayAdmin:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._owns_client = client is None
        self._client = client or loopback_client(timeout=10.0)
        self._logged_in = False

    async def __aenter__(self) -> GatewayAdmin:
        await self.login()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _check(self, operation: str, response: httpx.Response) -> None:
        if response.status_code != 200:
            raise GatewayError(
                operation,
                response.status_code,
                redact(response.text, (self._password,)),
            )

    async def login(self) -> None:
        if self._logged_in:
            return
        response = await self._client.post(
            f"{self.base_url}/gateway/auth/login",
            json={"email": self._email, "password": self._password},
        )
        self._check("auth/login", response)
        # The session cookie lives on the client from here on.
        self._logged_in = True

    async def bridges(self) -> list[GatewayBridge]:
        await self.login()
        response = await self._client.get(f"{self.base_url}/gateway/collaborations")
        self._check("collaborations", response)
        data: Any = response.json()
        items = data if isinstance(data, list) else data.get("collaborations", [])
        if not isinstance(items, list):
            raise GatewayError("collaborations", response.status_code, "expected a list of bridges")
        return [GatewayBridge.model_validate(item) for item in items]

    async def set_greetings(self, bridge_id: str, enabled: bool) -> None:
        await self.login()
        response = await self._client.patch(
            f"{self.base_url}/gateway/collaborations/{bridge_id}",
            json={"agent_greetings_enabled": enabled},
        )
        self._check("collaborations/patch", response)

    async def open_addressing(self, agent_id: str) -> None:
        await self.login()
        response = await self._client.put(
            f"{self.base_url}/gateway/agents/{agent_id}/addressing-policy",
            json={"policy": None},
        )
        self._check("agents/addressing-policy", response)
