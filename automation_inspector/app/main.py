from __future__ import annotations
import asyncio, json, logging, os, time
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.dependency_map import build_map

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CACHE_TTL = int(os.getenv("AI_CACHE_TTL", 86400))  # 24 hours
_CACHE_JSON: Optional[bytes] = None
_CACHE_TS: float = 0.0
_CACHE_LOCK = asyncio.Lock()

# ─── locate index.html ───────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent          # /app/app
CANDIDATES = [
    BASE_DIR.parent / "www" / "index.html",   # /app/www/index.html  ← your layout
    BASE_DIR / "www" / "index.html",
    BASE_DIR / "index.html",
    BASE_DIR / "ui" / "index.html",
    BASE_DIR / "static" / "index.html",
    BASE_DIR.parent / "index.html",
]
for path in CANDIDATES:
    if path.is_file():
        FRONTEND = path
        FRONTEND_DIR = path.parent
        break
else:
    FRONTEND = None
    FRONTEND_DIR = None
LOG.info("Front-end: %s", FRONTEND or "EMBEDDED fallback")

INLINE_HTML = """
<!doctype html><html><head><meta charset=utf-8>
<title>Automation Inspector – missing index.html</title></head>
<body style="font-family:sans-serif;margin:2rem">
<h1>Automation Inspector</h1>
<p style="color:#c00">index.html not found in the container.</p>
<p>Place it at <code>www/index.html</code> (root of the add-on image).</p>
</body></html>
"""

# ─── FastAPI setup ───────────────────────────────────────────────────────
app = FastAPI(title="Automation Inspector", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ─── helpers ─────────────────────────────────────────────────────────────
async def _rebuild_cache() -> None:
    global _CACHE_JSON, _CACHE_TS            # noqa: PLW0603
    LOG.info("Rebuilding dependency_map cache …")
    blob = await build_map()
    _CACHE_JSON = json.dumps(blob, separators=(",", ":")).encode()
    _CACHE_TS = time.time()
    LOG.info("✅ cache rebuilt: %d bytes · %s automations",
             len(_CACHE_JSON), len(blob["automations"]))

async def _refresh_loop() -> None:
    while True:
        try: await _rebuild_cache()
        except Exception as exc: LOG.exception("Background refresh failed: %s", exc)
        await asyncio.sleep(CACHE_TTL)

@app.on_event("startup")
async def _startup() -> None:
    await _rebuild_cache()
    asyncio.create_task(_refresh_loop(), name="ai_refresh_loop")

# ─── front-end routes ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def _index() -> HTMLResponse:
    if FRONTEND:
        return HTMLResponse(FRONTEND.read_text("utf-8"))
    return HTMLResponse(INLINE_HTML, status_code=200)

# ─── JSON endpoint ───────────────────────────────────────────────────────
@app.get("/dependency_map.json")
async def dependency_map(force: int = 0) -> Response:
    global _CACHE_JSON                       # noqa: PLW0603
    if force:
        async with _CACHE_LOCK:
            await _rebuild_cache()
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
