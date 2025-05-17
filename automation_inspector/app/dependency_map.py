import os, re, yaml, httpx, asyncio
from typing import Any, Dict, List

# ------------------------------------------------------------------ constants
HA_URL  = "http://supervisor/core"               # Supervisor’s proxy to HA
TOKEN   = os.getenv("SUPERVISOR_TOKEN")          # injected automatically
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(
    r"\b("
    r"sensor|binary_sensor|switch|light|climate|number|input_[a-z_]+|device_tracker"
    r")\.[0-9a-zA-Z_]+"
)

# ------------------------------------------------------------------ helpers
async def ha_get(path: str, *, json=False) -> Any | None:
    """GET through the Supervisor proxy. 404 ⇒ None."""
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json() if json else r.text

def collect_entities(obj: Any) -> List[str]:
    """Recursively scan strings / lists / dicts and return entity_ids found."""
    found: set[str] = set()
    if isinstance(obj, str):
        found.update(ENTITY_RE.findall(obj))
    elif isinstance(obj, list):
        for item in obj:
            found.update(collect_entities(item))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.update(collect_entities(v))
    return list(found)

# ------------------------------------------------------------------ main
async def build_map() -> Dict[str, dict]:
    states: List[dict] = await ha_get("/api/states", json=True)
    autos  = [s for s in states if s["entity_id"].startswith("automation.")]
    dep:   Dict[str, dict] = {}

    for st in autos:
        ent_id   = st["entity_id"]
        slug     = ent_id.split(".", 1)[1]
        nice     = st["attributes"].get("friendly_name", ent_id)

        # 1️⃣  try full YAML (works for YAML + UI automations)
        yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")
        if yaml_txt:
            try:
                yaml_obj = yaml.safe_load(yaml_txt) or {}
            except yaml.YAMLError:
                yaml_obj = {}
            entities = collect_entities(yaml_obj)
        else:
            # 2️⃣  fall back to attributes
            entities = collect_entities(st["attributes"])

        dep[ent_id] = {"friendly_name": nice, "entities": sorted(set(entities))}

    print(f"▶  dependency map built: {len(dep)} automations")
    return dep
