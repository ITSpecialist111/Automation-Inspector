from __future__ import annotations

import asyncio
import datetime
import json

import pytest

from app.ha_client import HomeAssistantConnectionError
from app.service import InspectionService, InspectionUnavailable
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


@pytest.mark.anyio
async def test_non_json_values_do_not_block_the_report() -> None:
    class DatedBuilder:
        async def build(self) -> dict[str, object]:
            return {"generated": datetime.date(2026, 9, 26)}

    service = InspectionService(DatedBuilder(), Settings())

    cached = await service.refresh()

    assert json.loads(cached.payload) == {"generated": "2026-09-26"}


class FailingBuilder:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def build(self) -> dict[str, int]:
        raise self.error


@pytest.mark.anyio
async def test_unexpected_startup_failure_logs_one_traceback_per_error(caplog) -> None:
    builder = FailingBuilder(ValueError("not enough values to unpack (expected 2, got 1)"))
    service = InspectionService(builder, Settings())

    for _ in range(2):
        with pytest.raises(InspectionUnavailable, match="ValueError: not enough values"):
            await service.refresh()
    builder.error = KeyError("entity_id")
    with pytest.raises(InspectionUnavailable, match="KeyError"):
        await service.refresh()

    tracebacks = [record for record in caplog.records if record.exc_info]
    assert [record.exc_info[0] for record in tracebacks if record.exc_info] == [
        ValueError,
        KeyError,
    ]


@pytest.mark.anyio
async def test_home_assistant_connection_failures_do_not_log_tracebacks(caplog) -> None:
    error = HomeAssistantConnectionError("Home Assistant is still starting")
    service = InspectionService(FailingBuilder(error), Settings())

    with pytest.raises(InspectionUnavailable, match="still starting"):
        await service.refresh()

    assert not [record for record in caplog.records if record.exc_info]
