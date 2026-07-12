from __future__ import annotations

import asyncio

import pytest

from app.service import InspectionService
from app.settings import Settings


class ControlledBuilder:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def build(self) -> dict[str, int]:
        self.calls += 1
        await asyncio.sleep(0.01)
        if self.fail:
            raise RuntimeError("Home Assistant offline")
        return {"generation": self.calls}


@pytest.mark.anyio
async def test_concurrent_refresh_is_coalesced() -> None:
    builder = ControlledBuilder()
    service = InspectionService(builder, Settings())

    first, second = await asyncio.gather(service.refresh(), service.refresh())

    assert builder.calls == 1
    assert first.generation == second.generation == 1
    assert first.etag == second.etag


@pytest.mark.anyio
async def test_refresh_failure_keeps_last_known_good_data() -> None:
    builder = ControlledBuilder()
    service = InspectionService(builder, Settings())
    first = await service.refresh()
    builder.fail = True

    stale = await service.refresh()

    assert stale.payload == first.payload
    assert "Home Assistant offline" in (service.last_error or "")
    assert service.status()["ready"] is True


class StartupBuilder:
    def __init__(self) -> None:
        self.calls = 0
        self.recovered = asyncio.Event()

    async def build(self) -> dict[str, bool]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Home Assistant is starting")
        self.recovered.set()
        return {"ready": True}


@pytest.mark.anyio
async def test_background_loop_retries_quickly_until_first_snapshot(monkeypatch) -> None:
    monkeypatch.setattr("app.service.STARTUP_RETRY_INTERVAL", 0.01)
    builder = StartupBuilder()
    service = InspectionService(builder, Settings(refresh_interval=3600))

    await service.start()
    try:
        await asyncio.wait_for(builder.recovered.wait(), timeout=1)
        assert service.current().generation == 1
        assert builder.calls == 2
    finally:
        await service.close()
