from __future__ import annotations

import re

import httpx
import pytest

from app.main import create_app
from app.service import InspectionService
from app.settings import Settings


class StaticBuilder:
    async def build(self) -> dict[str, object]:
        return {"schema_version": 2, "automations": {}, "orphans": []}


@pytest.mark.anyio
async def test_api_contract_security_headers_and_etag() -> None:
    settings = Settings(refresh_interval=3600)
    service = InspectionService(StaticBuilder(), settings)
    app = create_app(settings, service)
    transport = httpx.ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/api/v1/inspection")
        legacy = await client.get("/dependency_map.json")
        unchanged = await client.get(
            "/api/v1/inspection", headers={"If-None-Match": response.headers["etag"]}
        )
        health = await client.get("/health")
        ready = await client.get("/ready")
        status = await client.get("/api/v1/status")
        page = await client.get("/")

    assert response.status_code == 200
    assert response.json()["schema_version"] == 2
    assert legacy.json() == response.json()
    assert unchanged.status_code == 304
    assert health.status_code == 200
    assert ready.json()["ready"] is True
    assert status.json()["generation"] == 1
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
    assert "access-control-allow-origin" not in response.headers
    nonce = re.search(r'nonce="([A-Za-z0-9_-]+)"', page.text)
    assert nonce is not None
    assert "__CSP_NONCE__" not in page.text
    assert f"'nonce-{nonce.group(1)}'" in page.headers["content-security-policy"]


@pytest.mark.anyio
async def test_manual_refresh_increments_generation() -> None:
    settings = Settings(refresh_interval=3600)
    service = InspectionService(StaticBuilder(), settings)
    app = create_app(settings, service)
    transport = httpx.ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        initial = await client.get("/api/v1/inspection")
        refreshed = await client.get("/api/v1/inspection?refresh=true")

    assert initial.headers["x-automation-inspector-generation"] == "1"
    assert refreshed.headers["x-automation-inspector-generation"] == "2"


class FailingBuilder:
    async def build(self) -> dict[str, object]:
        raise RuntimeError("Home Assistant is starting")


@pytest.mark.anyio
async def test_api_returns_structured_unavailable_response() -> None:
    settings = Settings(refresh_interval=3600)
    service = InspectionService(FailingBuilder(), settings)
    app = create_app(settings, service)
    transport = httpx.ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/api/v1/inspection")
        ready = await client.get("/ready")

    assert response.status_code == 503
    assert "Home Assistant is starting" in response.json()["detail"]
    assert response.json()["status"]["ready"] is False
    assert ready.status_code == 503
