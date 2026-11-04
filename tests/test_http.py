"""The proxy rule: only loopback clients may ignore proxy environment settings."""

from __future__ import annotations

import httpx

from splitbrain.config import loopback_client


async def test_loopback_client_ignores_proxy_env() -> None:
    async with loopback_client() as client:
        assert client._trust_env is False


async def test_internet_clients_keep_httpx_defaults() -> None:
    async with httpx.AsyncClient() as client:
        assert client._trust_env is True
