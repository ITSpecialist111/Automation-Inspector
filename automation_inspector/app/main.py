"""FastAPI entry point for the Home Assistant Automation Inspector app."""

from __future__ import annotations

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import APP_VERSION
from app.dependency_map import DependencyMapBuilder
from app.service import InspectionService, InspectionUnavailable
from app.settings import Settings

LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

BASE_DIR = Path(__file__).resolve().parent
WWW_DIR = BASE_DIR.parent / "www"
INDEX_PATH = WWW_DIR / "index.html"

FALLBACK_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Automation Inspector</title></head><body><main><h1>Automation Inspector</h1>
<p>The web interface is missing from this app image.</p></main></body></html>"""


def create_app(
    settings: Settings | None = None,
    service: InspectionService | None = None,
) -> FastAPI:
    """Create an application instance, allowing isolated integration tests."""
    resolved_settings = settings or Settings.load()
    resolved_service = service or InspectionService(
        DependencyMapBuilder(resolved_settings), resolved_settings
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await resolved_service.start()
        yield
        await resolved_service.close()

    application = FastAPI(
        title="Automation Inspector",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.inspection_service = resolved_service
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    if WWW_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=WWW_DIR), name="static")

    @application.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
        )
        return response

    @application.get("/", response_class=HTMLResponse)
    @application.get("/index.html", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        if INDEX_PATH.is_file():
            nonce = secrets.token_urlsafe(18)
            html = INDEX_PATH.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
            return HTMLResponse(
                html,
                headers={
                    "Cache-Control": "no-cache",
                    "Content-Security-Policy": (
                        "default-src 'self'; "
                        f"script-src 'self' 'nonce-{nonce}'; "
                        "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                        "object-src 'none'; base-uri 'self'; form-action 'self'; "
                        "frame-ancestors 'self'"
                    ),
                },
            )
        return HTMLResponse(FALLBACK_HTML, headers={"Cache-Control": "no-cache"})

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION}

    @application.get("/ready")
    async def ready() -> Response:
        status = resolved_service.status()
        return JSONResponse(status, status_code=200 if status["ready"] else 503)

    @application.get("/api/v1/status")
    async def api_status() -> dict[str, object]:
        return resolved_service.status()

    @application.get("/api/v1/inspection")
    @application.get("/dependency_map.json", include_in_schema=False)
    async def inspection(
        refresh: bool = Query(False),
        force: int = Query(0, include_in_schema=False),
        if_none_match: str | None = Header(None),
    ) -> Response:
        try:
            cached = (
                await resolved_service.refresh()
                if refresh or bool(force)
                else resolved_service.current()
            )
        except InspectionUnavailable as exc:
            return JSONResponse(
                {
                    "detail": str(exc),
                    "status": resolved_service.status(),
                },
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )

        headers = {
            "Cache-Control": "no-cache",
            "ETag": cached.etag,
            "X-Automation-Inspector-Generation": str(cached.generation),
        }
        if resolved_service.last_error:
            headers["X-Automation-Inspector-Stale"] = "true"
        if if_none_match == cached.etag and not refresh and not force:
            return Response(status_code=304, headers=headers)
        return Response(cached.payload, media_type="application/json", headers=headers)

    return application


app = create_app()
