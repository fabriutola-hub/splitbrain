"""Integration smoke test: needs `uv run splitbrain up` (pytest -m integration)."""

from __future__ import annotations

import httpx
import pytest

from splitbrain.config import Settings


@pytest.mark.integration
async def test_switch_health_is_ok() -> None:
    settings = Settings.load()
    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.get(settings.health_url, timeout=5.0)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
