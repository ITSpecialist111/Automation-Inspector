"""Concurrency-safe inspection cache and refresh lifecycle."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol

from app.settings import Settings

LOG = logging.getLogger(__name__)
STARTUP_RETRY_INTERVAL = 10.0


class Builder(Protocol):
    async def build(self) -> dict[str, Any]: ...


class InspectionUnavailable(RuntimeError):
    """Raised when no successful inspection is available."""


@dataclass(frozen=True, slots=True)
class CachedInspection:
    payload: bytes
    etag: str
    generated_monotonic: float
    generation: int


class InspectionService:
    """Maintain a last-known-good inspection while refreshing in the background."""

    def __init__(self, builder: Builder, settings: Settings) -> None:
        self.builder = builder
        self.settings = settings
        self._cache: CachedInspection | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self.last_error: str | None = None
        self.last_attempt_monotonic: float | None = None
        self.last_success_monotonic: float | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._refresh_loop(), name="inspection-refresh")

    async def close(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _refresh_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.refresh()
            except InspectionUnavailable:
                LOG.warning("Home Assistant inspection unavailable: %s", self.last_error)

            delay = (
                self.settings.refresh_interval
                if self._cache is not None
                else STARTUP_RETRY_INTERVAL
            )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except TimeoutError:
                continue

    async def refresh(self) -> CachedInspection:
        observed_generation = self._cache.generation if self._cache else 0
        async with self._lock:
            if self._cache and self._cache.generation > observed_generation:
                return self._cache
            self.last_attempt_monotonic = time.monotonic()
            try:
                data = await self.builder.build()
                payload = json.dumps(
                    data,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                if self._cache is None:
                    raise InspectionUnavailable(self.last_error) from exc
                LOG.exception("Inspection refresh failed; retaining last-known-good data")
                return self._cache

            generation = observed_generation + 1
            etag = f'"{hashlib.sha256(payload).hexdigest()}"'
            now = time.monotonic()
            self._cache = CachedInspection(payload, etag, now, generation)
            self.last_error = None
            self.last_success_monotonic = now
            return self._cache

    def current(self) -> CachedInspection:
        if self._cache is None:
            raise InspectionUnavailable(self.last_error or "Inspection is not ready")
        return self._cache

    async def current_or_refresh(self) -> CachedInspection:
        """Return cached data, attempting recovery when no snapshot exists."""
        if self._cache is not None:
            return self._cache
        return await self.refresh()

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        age = now - self._cache.generated_monotonic if self._cache else None
        return {
            "ready": self._cache is not None,
            "generation": self._cache.generation if self._cache else 0,
            "age_seconds": round(age, 1) if age is not None else None,
            "stale": age is None or age > self.settings.refresh_interval * 2,
            "last_error": self.last_error,
            "refresh_interval": self.settings.refresh_interval,
        }
