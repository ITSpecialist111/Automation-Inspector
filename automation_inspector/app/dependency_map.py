"""
dependency_map.py – build { automation ➜ [ {id,state,ok} … ] } map
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
        for i in obj:
            found.update(collect_entities(i))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.update(collect_entities(v))
    return list(found)

# ---------------------------------------------------------------- main
async def build_map() -> Dict[str, dict]:
    states_raw = await ha_get("/api/states", json=True) or []
    state_map  = {row["entity_id"]: row for row in states_raw}
    autos      = [s for s in states_raw if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in autos:
        ent_id = st["entity_id"]
        nice   = st["attributes"].get("friendly_name", ent_id)
        numeric_id = st["attributes"].get("id")
        yaml_txt = None

        if numeric_id:
            yaml_txt = await ha_get(f"/api/config/automation/config/{numeric_id}")
        if yaml_txt is None:
            slug = ent_id.split(".", 1)[1]
            yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")

        if yaml_txt:
            try:
                yaml_obj = yaml.safe_load(yaml_txt) or {}
                ids = collect_entities(yaml_obj)
            except yaml.YAMLError:
                ids = []
        else:
            ids = collect_entities(st["attributes"])

        # build rich entity list with state + ok flag
        rich: List[dict] = []
        for eid in sorted(set(ids)):
            row   = state_map.get(eid)
            state = row["state"] if row else "unavailable"
            ok    = state not in ("unavailable", "unknown")
            rich.append({"id": eid, "state": state, "ok": ok})

        dep[ent_id] = {"friendly_name": nice, "entities": rich}

    print("▶ built map with", len(dep), "automations")
    return dep
