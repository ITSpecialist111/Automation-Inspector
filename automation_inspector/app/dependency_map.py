import os, re, httpx, asyncio, yaml
from typing import Dict, List, Any

HA_URL  = "http://supervisor/core"                     # proxy provided by Supervisor
TOKEN   = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(r"\b(?:sensor|binary_sensor|switch|input_\w+|number|device_tracker|light|climate)\.[\w\d_]+")

# ---------- helpers -----------------------------------------------------------

async def ha_get(path: str, *, json=False, ok_404=False) -> Any:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        if ok_404 and r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json() if json else r.text

def deep_find_entity_ids(obj: Any) -> List[str]:
    """Recursively walk any list/dict/str and return matching entity IDs."""
    found: set[str] = set()
    if isinstance(obj, str):
        found.update(ENTITY_RE.findall(obj))
    elif isinstance(obj, list):
        for item in obj:
            found.update(deep_find_entity_ids(item))
    elif isinstance(obj, dict):
        for val in obj.values():
            found.update(deep_find_entity_ids(val))
    return list(found)

# ---------- main builder ------------------------------------------------------

async def build_map() -> Dict[str, dict]:
    states: List[dict] = await ha_get("/api/states", json=True)
    automations = [s for s in states if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for a in automations:
        ent_id   = a["entity_id"]
        slug     = ent_id.split(".", 1)[1]
        friendly = a["attributes"].get("friendly_name", ent_id)

        # 1. try full YAML via REST (works for UI + YAML automations)
        yaml_text = await ha_get(f"/api/config/automation/config/{slug}", ok_404=True)
        if yaml_text:
            try:
                yaml_obj = yaml.safe_load(yaml_text)
                entities  = deep_find_entity_ids(yaml_obj)
            except yaml.YAMLError:
                entities = []
        else:
            # 2. fallback: scan the attributes dict
            entities = deep_find_entity_ids(a["attributes"])

        dep[ent_id] = {"friendly_name": friendly, "entities": sorted(set(entities))}

    return dep
