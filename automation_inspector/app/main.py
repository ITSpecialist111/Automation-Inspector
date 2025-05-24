"""
main.py – FastAPI entry-point for the add-on.
"""

from __future__ import annotations

import asyncio
from time import time
from typing import Any, Dict, List, Set

from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from starlette.requests import Request
import uvicorn
import os
import json
import logging
from .dependency_map import build_map
from .renderer import lovelace_from_map

_LOGGER = logging.getLogger(__name__)

app  = FastAPI()
CACHE: Dict[str, tuple[Any, float]] = {}
IGNORED: Set[str] = set()          # ids suppressed in /alerts


# ───────────────────────────── helper ─────────────────────────────
def _cached(key: str, ttl: int, builder):
    now = time()
    if key not in CACHE or now - CACHE[key][1] > ttl:
        CACHE[key] = (builder(), now)
    return CACHE[key][0]


# ───────────────────────────── routes ─────────────────────────────
@app.get("/dependency_map.json")
async def dependency_map():
    dep_map = _cached("MAP", 30, lambda: asyncio.run(build_map()))
    return JSONResponse(dep_map)


@app.get("/dashboard.yaml")
async def dashboard_yaml():
    dep_map = _cached("MAP", 30, lambda: asyncio.run(build_map()))
    yaml    = _cached("YAML", 30, lambda: lovelace_from_map(dep_map))
    return PlainTextResponse(yaml, media_type="text/yaml")


@app.get("/orphaned_helpers.json")
async def orphaned_helpers():
    def _builder():
        dep_map   = asyncio.run(build_map())
        used      = set(sum((v["entities"] for v in dep_map.values()), []))
        all_states = asyncio.run(build_map.__globals__['ha_get']("/states"))
        helpers   = [
            s["entity_id"] for s in all_states
            if s["entity_id"].split(".")[0] in (
                "input_boolean", "input_number", "input_text",
                "input_select", "input_datetime"
            )
        ]
        return sorted(h for h in helpers if h not in used)
    return JSONResponse(_cached("ORPHANS", 300, _builder))


# ─────────── alerts & suppression (simple, in-memory) ────────────
def _collect_alerts() -> List[dict]:
    dep_map = _cached("MAP", 30, lambda: asyncio.run(build_map()))
    alerts: List[dict] = []

    for aid, info in dep_map.items():
        if info["unknown_triggers"] and aid not in IGNORED:
            alerts.append({"source": aid, "type": "unknown_trigger", "details": info["unknown_triggers"]})

        if info["offline_members"] and aid not in IGNORED:
            alerts.append({"source": aid, "type": "offline_members", "details": info["offline_members"]})

        if info["stale_days"] is not None and \
           info["stale_days"] >= info["stale_threshold"] and aid not in IGNORED:
            alerts.append({"source": aid, "type": "stale", "days": info["stale_days"]})

    return alerts


@app.get("/alerts")
async def alerts():
    return JSONResponse(_collect_alerts())


@app.post("/ignore")
async def ignore(alert: dict):
    if "id" not in alert:
        raise HTTPException(400, "missing id")
    IGNORED.add(alert["id"])
    return {"ignored": list(IGNORED)}


@app.post("/unignore")
async def unignore(alert: dict):
    IGNORED.discard(alert.get("id"))
    return {"ignored": list(IGNORED)}


# ───────────────────────── static UI ─────────────────────────────
@app.get("/{path:path}")
async def root(path: str = ""):
    ui = os.path.join(os.path.dirname(__file__), "..", "www", "index.html")
    return FileResponse(ui)


# ──────────────────────────── run ────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("automation_inspector.app.main:app", host="0.0.0.0", port=3000, reload=False)
