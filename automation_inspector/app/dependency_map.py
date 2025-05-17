import os, re, yaml, httpx
from typing import Any, Dict, List

HA_URL  = "http://supervisor/core"                 # Supervisor proxy to HA
TOKEN   = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ------------------------------------------------------------------ helpers
async def ha_get(path: str, *, json=False) -> Any | None:
    """GET via Supervisor proxy. Return None on 403 / 404 so we can fall back."""
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        if r.status_code in (403, 404):
            return None
        r.raise_for_status()
        return r.json() if json else r.text

ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|input_\w+|device_tracker)\.[0-9A-Za-z_]+"
)

def collect_entities(obj: Any) -> List[str]:
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
    states = await ha_get("/api/states", json=True) or []
    autos  = [s for s in states if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in autos:
        ent_id = st["entity_id"]
        slug   = ent_id.split(".", 1)[1]
        nice   = st["attributes"].get("friendly_name", ent_id)

        yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")
        if yaml_txt:                                  # full YAML available
            try:
                yaml_obj = yaml.safe_load(yaml_txt) or {}
                entities = collect_entities(yaml_obj)
                print(f"yaml OK   – {slug:<40} ({len(entities)} entities)")
            except yaml.YAMLError:
                entities = []
        else:                                         # fall back to attributes
            entities = collect_entities(st["attributes"])
            print(f"yaml miss → {slug:<40} ({len(entities)} entities)")

        dep[ent_id] = {"friendly_name": nice, "entities": sorted(set(entities))}

    print("▶ built map with", len(dep), "automations")
    return dep
