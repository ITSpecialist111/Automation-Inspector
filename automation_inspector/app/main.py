import asyncio
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from .dependency_map import build_map
from .renderer import lovelace_from_map
import os

app = FastAPI()
CACHE = {}
CACHE_TTL = 30  # seconds

async def get_map():
    now = asyncio.get_event_loop().time()
    if CACHE and now - CACHE["ts"] < CACHE_TTL:
        return CACHE["data"]
    data = await build_map()
    CACHE.update({"data": data, "ts": now})
    return data

# ----------------- API endpoints -----------------
@app.get("/dependency_map.json")
async def dep_map():
    return JSONResponse(await get_map())

@app.get("/dashboard.yaml")
async def dashboard_yaml():
    data = await get_map()
    yaml_str = lovelace_from_map(data)
    return PlainTextResponse(yaml_str, media_type="text/yaml")

# ----------------- Front-end assets ---------------
@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "www", "index.html"))
