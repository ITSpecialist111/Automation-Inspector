from __future__ import annotations
import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Tuple

import httpx
import yaml

LOG = logging.getLogger(__name__)
HA_URL = "http://supervisor/core"
TOKEN  = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|"
    r"input_\w+|device_tracker)\.[0-9A-Za-z_]+\b"
)

# ---------------------------------------------------------------- helpers
async def ha_get(path: str, *, json: bool = False) -> Any | None:
    """
    Async GET to the HA API.
    • Returns parsed JSON (json=True) or text.
    • 403, 404 or any 5xx ⇒ None (treated as “missing/disabled”).
    """
    async with httpx.AsyncClient() as cli:
        try:
            resp = await cli.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        except httpx.RequestError as exc:
            LOG.warning("HTTP request failed %s: %s", path, exc)
            return None

        if resp.status_code in (403, 404) or resp.status_code >= 500:
            return None

        resp.raise_for_status()
        return resp.json() if json else resp.text


def collect_entities(obj: Any) -> List[str]:
    """Recursively find all entity IDs in nested data structures."""
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
    dep_map: Dict[str, dict],
) -> List[str]:
    """Return all input_* helpers not referenced by any automation."""
    helpers    = {eid for eid in state_map if eid.startswith("input_")}
    referenced = {
        ent["id"]
        for info in dep_map.values()
        for ent in info.get("entities", [])
    }
    return sorted(helpers - referenced)

# ---------------------------------------------------------------- main
async def process_automation(st: Dict[str, Any], state_map: Dict[str, Any]) -> Tuple[str, dict] | None:
    """Return (entity_id, info) or None if irrecoverable error occurred."""
    ent_id    = st["entity_id"]
    nice      = st["attributes"].get("friendly_name", ent_id)
    enabled   = (st["state"] == "on")
    config_id = st["attributes"].get("id")
    last      = state_map.get(ent_id, {}).get("attributes", {}).get("last_triggered")

    # ---- fetch YAML (may legitimately be None)
    yaml_txt: str | None = None
    try:
        if config_id:
            yaml_txt = await ha_get(f"/api/config/automation/config/{config_id}")
        if yaml_txt is None:
            slug     = ent_id.split(".", 1)[1]
            yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Failed to fetch YAML for %s: %s", ent_id, exc)
        yaml_txt = None

    # ---- extract entities
    try:
        ids = collect_entities(
            yaml.safe_load(yaml_txt) if yaml_txt else st["attributes"]
        )
    except yaml.YAMLError as exc:
        LOG.warning("YAML parse error in %s: %s", ent_id, exc)
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
        "friendly_name":  nice,
        "enabled":        enabled,
        "config_id":      config_id,
        "last_triggered": last,
        "entities":       rich,
    }


async def build_map() -> Dict[str, Any]:
    """Build dependency map + orphan list for /dependency_map.json."""
    states_raw = await ha_get("/api/states", json=True) or []
    state_map  = {row["entity_id"]: row for row in states_raw}
    autos      = [s for s in states_raw if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    # ---- fan-out with exception capture
    tasks = [
        process_automation(st, state_map)
        for st in autos
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    skipped = 0
    for res in results:
        if isinstance(res, Exception):
            skipped += 1
            LOG.warning("Skipped automation due to error: %s", res)
            continue
        if res is None:
            skipped += 1
            continue
        ent_id, info = res
        dep[ent_id] = info

    orphans = await find_orphaned_helpers(state_map, dep)
    LOG.info(
        "▶ built map with %s automations, %s orphaned helpers (skipped %s)",
        len(dep), len(orphans), skipped,
    )
    return {"automations": dep, "orphans": orphans}


# compatibility for legacy imports
build_dependency_map = build_map