"""
dependency_map.py – builds the JSON served at /dependency_map.json

Adds for v0.3.1:
  • 'enabled'   – True/False automation state
  • 'config_id' – numeric id used by /config/automation/edit/<id> (Trace button)

v0.3.4 change:
  • suppress false-positive “entities” (services, non-existent IDs)

v0.3.9 change:
  • add 'last_triggered' – timestamp of when each automation last ran
  • add orphan detection for input_* helpers
"""

from __future__ import annotations
import os
import re
import yaml
import httpx
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
    """Recursively find all entity IDs in a dict/list/str."""
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


async def find_orphaned_helpers(
    state_map: Dict[str, Any],
    dep_map: Dict[str, dict]
) -> List[str]:
    """
    Return a sorted list of all input_* helpers that are not referenced
    by any automation in dep_map.
    """
    # 1) gather all helpers in HA
    all_helpers = {eid for eid in state_map if eid.startswith("input_")}
    # 2) gather all entities referenced by automations
    referenced = set()
    for info in dep_map.values():
        for ent in info.get("entities", []):
            referenced.add(ent["id"])
    # 3) orphans = helpers minus referenced
    orphans = sorted(all_helpers - referenced)
    return orphans

# ---------------------------------------------------------------- main
async def build_map() -> Dict[str, Any]:
    # fetch all entity states
    states_raw = await ha_get("/api/states", json=True) or []
    state_map  = {row["entity_id"]: row for row in states_raw}
    autos      = [s for s in states_raw if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in autos:
        ent_id    = st["entity_id"]
        nice      = st["attributes"].get("friendly_name", ent_id)
        enabled   = (st["state"] == "on")
        config_id = st["attributes"].get("id")

        # extract last_triggered timestamp (ISO 8601 string or None)
        last = None
        if ent_id in state_map:
            last = state_map[ent_id]["attributes"].get("last_triggered")

        # load YAML config to collect entity references
        yaml_txt = None
        if config_id:
            yaml_txt = await ha_get(f"/api/config/automation/config/{config_id}")
        if yaml_txt is None:
            slug = ent_id.split(".", 1)[1]
            yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")

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
            "enabled":       enabled,
            "config_id":     config_id,
            "last_triggered": last,
            "entities":      rich,
        }

    # find orphaned helpers
    orphans = await find_orphaned_helpers(state_map, dep)
    print(f"▶ built map with {len(dep)} automations, {len(orphans)} orphaned helpers")

    # return both automations and orphan list
    return {"automations": dep, "orphans": orphans}
