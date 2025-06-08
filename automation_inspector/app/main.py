from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the new async builder (alias left in dependency_map for compatibility)
from app.dependency_map import build_map

app = FastAPI(
    title="Automation Inspector",
    docs_url=None,
    redoc_url=None,
)

# If your add-on already has other middleware or routes, keep them;
# nothing below interferes with existing code.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/dependency_map.json")
async def dependency_map():
    """
    Return the JSON consumed by the front-end table.
    build_map() is fully async and already handles all caching/parallelism.
    """
    return await build_map()