from __future__ import annotations
import asyncio
import os
import re
from typing import Any, Dict, List

import httpx
import yaml

HA_URL  = "http://supervisor/core"
TOKEN   = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|"
    r"input_\w+|device_tracker)\.[0-9A-Za-z_]+\b"
)

# ---------------------------------------------------------------- helpers
async def ha_get(path: str, *, json: bool = False) -> Any | None:
    """
    Thin async wrapper around a GET to Home-Assistant’s HTTP API.

    Returns   – parsed JSON if json=True, otherwise raw text.
    On 403/404 – returns None (the API does that when an automation is disabled).
    """
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
    referenced = {
        ent["id"]
        for info in dep_map.values()
        for ent in info.get("entities", [])
    }
    # 3) orphans = helpers minus referenced
    return sorted(all_helpers - referenced)

# ---------------------------------------------------------------- main
async def build_map() -> Dict[str, Any]:
    """Return the dependency map + orphan list used by /dependency_map.json."""
    # ---------------------------------------------------------------- states
    states_raw = await ha_get("/api/states", json=True) or []
    state_map  = {row["entity_id"]: row for row in states_raw}
    autos      = [s for s in states_raw if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    # ---------------------------------------------------------------- worker
    async def process_automation(st: Dict[str, Any]) -> tuple[str, dict]:
        """
        Build the per-automation entry for the dependency map.

        Returned as (entity_id, info_dict) so the gather() result can be folded
        straight back into the main 'dep' dict.
        """
        ent_id    = st["entity_id"]
        nice      = st["attributes"].get("friendly_name", ent_id)
        enabled   = (st["state"] == "on")
        config_id = st["attributes"].get("id")
        last      = state_map.get(ent_id, {}).get("attributes", {}).get("last_triggered")

        # ---------------- YAML fetch (may be None for disabled automations)
        yaml_txt: str | None = None
        if config_id:
            yaml_txt = await ha_get(f"/api/config/automation/config/{config_id}")
        if yaml_txt is None:  # fall-back to slug, covers blueprints / old HA versions
            slug     = ent_id.split(".", 1)[1]
            yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")

        # ---------------- entity extraction
        try:
            ids = collect_entities(
                yaml.safe_load(yaml_txt) if yaml_txt else st["attributes"]
            )
        except yaml.YAMLError:
            ids = []

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

        return ent_id, {
            "friendly_name": nice,
            "enabled":       enabled,
            "config_id":     config_id,
            "last_triggered": last,
            "entities":      rich,
        }

    # ---------------------------------------------------------------- fan-out
    results = await asyncio.gather(*[process_automation(st) for st in autos])
    dep.update(dict(results))

    # ---------------------------------------------------------------- orphans
    orphans = await find_orphaned_helpers(state_map, dep)
    print(f"▶ built map with {len(dep)} automations, {len(orphans)} orphaned helpers")

    return {"automations": dep, "orphans": orphans}