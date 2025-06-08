# app/main.py
"""
FastAPI entry-point for the Automation Inspector add-on.

Improvements over stock version:
  • builds dependency map once on start-up (“warm-up”)
  • responds from an in-memory cache
  • background task refreshes the cache every CACHE_TTL seconds
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.dependency_map import build_map

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---- cache settings ----------------------------------------------------
CACHE_TTL = int(os.getenv("AI_CACHE_TTL", 300))      # seconds between refreshes
_CACHE_JSON: Optional[bytes] = None                  # gzip not needed, CF does it
_CACHE_TS: float = 0.0                               # unix-epoch of last build
_CACHE_LOCK = asyncio.Lock()

# ---- FastAPI setup ------------------------------------------------------
app = FastAPI(
    title="Automation Inspector",
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- helper -------------------------------------------------------------
async def _rebuild_cache() -> None:
    """Rebuild the dependency map and store as UTF-8 JSON bytes."""
    global _CACHE_JSON, _CACHE_TS  # pylint: disable=global-statement
    LOG.info("Rebuilding dependency_map cache …")
    blob = await build_map()
    _CACHE_JSON = json.dumps(blob, separators=(",", ":")).encode()
    _CACHE_TS = time.time()
    LOG.info("✅ cache rebuilt: %d bytes, %s automations",
             len(_CACHE_JSON), len(blob["automations"]))

async def _refresh_loop() -> None:
    """Background task that keeps the cache warm."""
    while True:
        try:
            await _rebuild_cache()
        except Exception as exc:  # noqa: BLE001
            LOG.exception("Background refresh failed: %s", exc)
        await asyncio.sleep(CACHE_TTL)

# ---- startup event ------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    # Build once before we start listening
    await _rebuild_cache()
    # Kick off periodic refresh loop
    asyncio.create_task(_refresh_loop(), name="ai_refresh_loop")

# ---- route handler ------------------------------------------------------
@app.get("/dependency_map.json")
async def dependency_map() -> Response:
    """
    Return cached dependency map JSON. If the cache is stale and the background
    task hasn’t refreshed yet, rebuild synchronously (rare).
    """
    global _CACHE_JSON  # pylint: disable=global-statement
    if _CACHE_JSON is None or time.time() - _CACHE_TS > CACHE_TTL * 1.5:
        # extra 50 % grace so the background loop has time; guarded by lock
        async with _CACHE_LOCK:
            if _CACHE_JSON is None or time.time() - _CACHE_TS > CACHE_TTL * 1.5:
                await _rebuild_cache()

    return Response(
        content=_CACHE_JSON,
        media_type="application/json",
        headers={
            "Cache-Control": f"max-age={CACHE_TTL}",
            "ETag": f"W/\"{_CACHE_TS:.0f}\"",
        },
    )