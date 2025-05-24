"""
main.py – FastAPI entry-point for the Automation-Inspector add-on.
"""

from __future__ import annotations

import asyncio
import json
import os
from time import time
from typing import Any, Dict, List, Set

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from .dependency_map import build_map
from .renderer import lovelace_from_map

app = FastAPI()
CACHE: Dict[str, tuple[Any, float]] = {}   # key -> (value, ts)
IGNORED: Set[str] = set()                  # user-suppressed alert IDs
TTL = 30                                   # seconds – cache for map & yaml


# ─────────────────────────── helpers ────────────────────────────
async def get_map_cached() -> dict:
    now = time()
    if "MAP" not in CACHE or now - CACHE["MAP"][1] > TTL:
        CACHE["MAP"] = (await build_map(), now)
    return CACHE["MAP"][0]


def cache_set(key: str, value: Any) -> None:
    CACHE[key] = (value, time())


def cache_get(key: str, ttl: int | None = None) -> Any | None:
    if key not in CACHE:
        return None
    if ttl is not None and time() - CACHE[key][1] > ttl:
        return None
    return CACHE[key][0]


# ───────────────────────────── routes ───────────────────────────
@app.get("/dependency_map.json")
async def dependency_map():
    return JSONResponse(await get_map_cached())


@app.get("/dashboard.yaml")
async def dashboard_yaml():
    yaml = cache_get("YAML", TTL)
    if yaml is None:
        yaml = lovelace_from_map(await get_map_cached())
        cache_set("YAML", yaml)
    return PlainTextResponse(yaml, media_type="text/yaml")


@app.get("/orphaned_helpers.json")
async def orphaned_helpers():
    cached = cache_get("ORPHANS", 300)
    if cached is not None:
        return JSONResponse(cached)

    dep_map = await get_map_cached()
    used = set(sum((v["entities"] for v in dep_map.values()), []))

    # live call for all states
    states = await build_map.__globals__["ha_get"]("/states")
    helpers = [
        s["entity_id"]
        for s in states
        if s["entity_id"].split(".")[0]
        in (
            "input_boolean",
            "input_number",
            "input_text",
            "input_select",
            "input_datetime",
        )
    ]
    orphans = sorted(h for h in helpers if h not in used)
    cache_set("ORPHANS", orphans)
    return JSONResponse(orphans)


# ───────── alerts & suppression ─────────
# … file header unchanged …
def collect_alerts(map_data: dict) -> List[dict]:
    alerts=[]
    for aid, info in map_data.items():
        if aid.startswith("_"):       # skip summary
            continue
        if info.get("unknown_triggers") and aid not in IGNORED:
            alerts.append({"id": aid, "type": "unknown", "details": info["unknown_triggers"]})
        if info.get("offline_members") and aid not in IGNORED:
            alerts.append({"id": aid, "type": "offline", "details": info["offline_members"]})
        if (sd:=info.get("stale_days")) is not None and sd>=info["stale_threshold"] and aid not in IGNORED:
            alerts.append({"id": aid, "type": "stale", "days": sd})
    return alerts
# … rest of file unchanged …



@app.get("/alerts")
async def alerts():
    return JSONResponse(collect_alerts(await get_map_cached()))


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


# ───────────── static UI ─────────────
@app.get("/{path:path}")
async def root(path: str = ""):
    ui = os.path.join(os.path.dirname(__file__), "..", "www", "index.html")
    return FileResponse(ui)


# ─────────────────────────── run ────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "automation_inspector.app.main:app",
        host="0.0.0.0",
        port=1234,
        reload=False,
    )
