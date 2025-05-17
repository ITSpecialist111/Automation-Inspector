import os, re, yaml, httpx
from typing import Any, Dict, List

HA_URL  = "http://supervisor/core"
TOKEN   = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Full entity-id, NOT a capturing group
ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|input_\w+|device_tracker)\.[0-9a-zA-Z_]+"
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

async def build_map() -> Dict[str, dict]:
    states = await ha_get("/api/states", json=True)
    automations = [s for s in states if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in automations:
        ent_id = st["entity_id"]
        slug   = ent_id.split(".", 1)[1]
        nice   = st["attributes"].get("friendly_name", ent_id)

        yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")
        if yaml_txt:
            try:
                yaml_obj = yaml.safe_load(yaml_txt) or {}
                entities  = collect_entities(yaml_obj)
                print(f"yaml OK  – {slug:40} ({len(entities)} entities)")
            except yaml.YAMLError:
                entities = []
        else:
            entities = collect_entities(st["attributes"])
            print(f"yaml 404 → fallback for {slug:40} ({len(entities)} entities)")

        dep[ent_id] = {"friendly_name": nice, "entities": sorted(set(entities))}

    print("▶  built map with", len(dep), "automations")
    return dep
