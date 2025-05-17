"""
dependency_map.py  –  Build {automation ➜ entities} map

Works for:
  • UI automations   (fetch by attributes.id)
  • YAML automations (same id also present)
Falls back to state attributes when /config API is blocked.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

import httpx
import yaml

# ----------------------------------------------------------------- constants
HA_URL  = "http://supervisor/core"                 # Supervisor proxy to HA
TOKEN   = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|"
    r"input_\w+|device_tracker)\.[0-9A-Za-z_]+\b"
)

# ----------------------------------------------------------------- helpers
async def ha_get(path: str, *, json: bool = False) -> Any | None:
    """
    GET <HA_URL><path> via Supervisor proxy.
    403 / 404 → return None so caller can fall back gracefully.
    """
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        if r.status_code in (403, 404):
            return None
        r.raise_for_status()
        return r.json() if json else r.text


def collect_entities(obj: Any) -> List[str]:
    """Recursively collect entity_ids from str / list / dict."""
    found: set[str] = set()

    if obj is None:
        return []

    if isinstance(obj, str):
        found.update(ENTITY_RE.findall(obj))

    elif isinstance(obj, list):
        for item in obj:
            found.update(collect_entities(item))

    elif isinstance(obj, dict):
        for key, val in obj.items():
            # Explicitly follow 'entity_id' keys, but also walk every value
            found.update(collect_entities(val))

    return list(found)

# ----------------------------------------------------------------- main
async def build_map() -> Dict[str, dict]:
    states = await ha_get("/api/states", json=True) or []
    autos  = [s for s in states if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in autos:
        ent_id = st["entity_id"]                     # automation.dishwasher_status_yes
        nice   = st["attributes"].get("friendly_name", ent_id)

        # Use the internal numeric id when available – required for UI automations
        numeric_id = st["attributes"].get("id")      # e.g. 1684872402573
        yaml_txt   = None

        if numeric_id is not None:
            yaml_txt = await ha_get(f"/api/config/automation/config/{numeric_id}")

        # If that failed (rare) try the old slug fallback
        if yaml_txt is None:
            slug = ent_id.split(".", 1)[1]           # dishwasher_status_yes
            yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")

        # ---------------------------------------------------------------- parse
        if yaml_txt:
            try:
                yaml_obj = yaml.safe_load(yaml_txt) or {}
                entities = collect_entities(yaml_obj)
                print(f"yaml OK   – {numeric_id or slug:<15} ({len(entities)} entities)")
            except yaml.YAMLError:
                entities = []
        else:
            # Fall back to attributes of state object (very limited info)
            entities = collect_entities(st["attributes"])
            print(f"yaml miss → {nice:<40} ({len(entities)} entities)")

        dep[ent_id] = {
            "friendly_name": nice,
            "entities": sorted(set(entities)),
        }

    print("▶ built map with", len(dep), "automations")
    return dep
