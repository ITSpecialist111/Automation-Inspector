"""
dependency_map.py – builds the JSON served at /dependency_map.json

Adds for v0.3.1:
  • 'enabled'   – True/False automation state
  • 'config_id' – numeric id used by /config/automation/edit/<id> (Trace button)

v0.3.4 change:
  • suppress false-positive “entities” (services, non-existent IDs)
"""

from __future__ import annotations
import os, re, yaml, httpx
from typing import Any, Dict, List

HA_URL  = "http://supervisor/core"
TOKEN   = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|"
    r"input_\w+|device_tracker)\.[0-9A-Za-z_]+\b"
)

# ---------------------------------------------------------------- helpers
async def ha_get(path: str, *, json: bool = False) -> Any | None:
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        if r.status_code in (403, 404):
            return None
        r.raise_for_status()
        return r.json() if json else r.text


def collect_entities(obj: Any) -> List[str]:
    found: set[str] = set()
    if obj is None:
        return []
    if isinstance(obj, str):
        found.update(ENTITY_RE.findall(obj))
    elif isinstance(obj, list):
        for item in obj:
            found.update(collect_entities(item))
    elif isinstance(obj, dict):
        for val in obj.values():
            found.update(collect_entities(val))
    return list(found)

# ---------------------------------------------------------------- main
async def build_map() -> Dict[str, dict]:
    states_raw = await ha_get("/api/states", json=True) or []
    state_map  = {row["entity_id"]: row for row in states_raw}
    autos      = [s for s in states_raw if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in autos:
        ent_id   = st["entity_id"]
        nice     = st["attributes"].get("friendly_name", ent_id)
        enabled  = (st["state"] == "on")
        config_id = st["attributes"].get("id")            # numeric id
        yaml_txt  = None

        if config_id:
            yaml_txt = await ha_get(f"/api/config/automation/config/{config_id}")
        if yaml_txt is None:                              # fallback by slug
            slug = ent_id.split(".", 1)[1]
            yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")

        # extract raw IDs from YAML or attributes
        if yaml_txt:
            try:
                ids = collect_entities(yaml.safe_load(yaml_txt) or {})
            except yaml.YAMLError:
                ids = []
        else:
            ids = collect_entities(st["attributes"])

        # build rich entity list with state + ok flag,
        # suppress false positives (services, non-existent IDs)
        rich: List[dict] = []
        seen = set()
        for eid in sorted(ids):
            if eid in seen or eid not in state_map:
                continue
            seen.add(eid)
            row   = state_map[eid]
            state = row["state"]
            ok    = state not in ("unavailable", "unknown")
            rich.append({"id": eid, "state": state, "ok": ok})

        dep[ent_id] = {
            "friendly_name": nice,
            "enabled": enabled,
            "config_id": config_id,
            "entities": rich,
        }

    print("▶ built map with", len(dep), "automations")
    return dep
