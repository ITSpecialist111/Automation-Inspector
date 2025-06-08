# app/main.py
"""
Automation Inspector – FastAPI back-end

• Builds dependency map once at start-up (“warm-up”)
• Serves subsequent requests from an in-memory cache
• Background task refreshes the cache every CACHE_TTL seconds
• ?force=1 on /dependency_map.json triggers an immediate rebuild
• Root path (/) and /index.html now return the front-end file, so
  the add-on works via direct IP:PORT as well as Ingress.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.dependency_map import build_map

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------- cache settings
CACHE_TTL = int(os.getenv("AI_CACHE_TTL", 300))           # seconds between refreshes
_CACHE_JSON: Optional[bytes] = None                       # gzip handled by proxy
_CACHE_TS: float = 0.0                                    # unix-epoch of last build
_CACHE_LOCK = asyncio.Lock()

# Where the front-end lives
BASE_DIR = Path(__file__).parent           # /app/app
FRONTEND = BASE_DIR / "index.html"         # keep index.html beside main.py

# ---------------------------------------------------------------- FastAPI
app = FastAPI(title="Automation Inspector", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------- helpers
async def _rebuild_cache() -> None:
    """Rebuild the dependency map and store as UTF-8 JSON bytes."""
    global _CACHE_JSON, _CACHE_TS                                       # noqa: PLW0603
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
        except Exception as exc:                                        # noqa: BLE001
            LOG.exception("Background refresh failed: %s", exc)
        await asyncio.sleep(CACHE_TTL)

# ---------------------------------------------------------------- start-up
@app.on_event("startup")
async def _startup() -> None:
    await _rebuild_cache()                       # warm-up build
    asyncio.create_task(_refresh_loop(), name="ai_refresh_loop")

# ---------------------------------------------------------------- static front-end
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def _index() -> FileResponse:             # noqa: D401
    """Return the front-end HTML file."""
    return FileResponse(FRONTEND)

# ---------------------------------------------------------------- JSON endpoint
@app.get("/dependency_map.json")
async def dependency_map(force: int = 0) -> Response:
    """
    Return dependency-map JSON.

    • cached path – fast
    • `?force=1`   – synchronous rebuild (bypasses cache)
    """
    global _CACHE_JSON                                                # noqa: PLW0603

    # manual rebuild requested
    if force:
        async with _CACHE_LOCK:
            await _rebuild_cache()

    # stale-cache safety net
    if _CACHE_JSON is None or time.time() - _CACHE_TS > CACHE_TTL * 1.5:
        async with _CACHE_LOCK:
            if _CACHE_JSON is None or time.time() - _CACHE_TS > CACHE_TTL * 1.5:
                await _rebuild_cache()

    return Response(
        content=_CACHE_JSON,
        media_type="application/json",
        headers={
            "Cache-Control": f"max-age={CACHE_TTL}",
            "ETag": f'W/"{_CACHE_TS:.0f}"',
        },
    )