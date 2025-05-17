"""
dependency_map.py – build a map of  ↔  entities used by every automation

Works for:
  • YAML automations   – via /api/config/automation/config/<slug>
  • UI automations     – falls back to attributes
Handles:
  • plain strings
  • lists of strings
  • dicts (walks nested 'entity_id' keys)
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

import httpx
import yaml

# ------------------------------------------------------------------- constants
HA_URL = "http://supervisor/core"                 # Supervisor proxy to Home-Assistant
TOKEN  = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENTITY_RE = re.compile(
    r"\b(?:sensor|binary_sensor|switch|light|climate|number|"
    r"input_\w+|device_tracker)\.[0-9A-Za-z_]+\b"
)

# -------------------------------------------------------------------- helpers
async def ha_get(path: str, *, json: bool = False) -> Any | None:
    """
    GET <HA_URL><path> through the Supervisor proxy.

    Returns:
        • parsed JSON / raw text
        • None if API returns 403 or 404
    """
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{HA_URL}{path}", headers=HEADERS, timeout=30)
        if r.status_code in (403, 404):
            return None
        r.raise_for_status()
        return r.json() if json else r.text


def collect_entities(obj: Any) -> List[str]:
    """Recursively walk an object and pull out entity_ids."""
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
            # if the key itself is `entity_id` treat the value specially
            if key == "entity_id":
                found.update(collect_entities(val))
            else:
                found.update(collect_entities(val))

    return list(found)


# -------------------------------------------------------------------- main
async def build_map() -> Dict[str, dict]:
    """
    Returns:
        {
          "automation.xyz": {
              "friendly_name": "My automation",
              "entities": ["sensor.a", "binary_sensor.b"]
          },
          ...
        }
    """
    states = await ha_get("/api/states", json=True) or []
    autos  = [s for s in states if s["entity_id"].startswith("automation.")]
    dep: Dict[str, dict] = {}

    for st in autos:
        ent_id = st["entity_id"]
        slug   = ent_id.split(".", 1)[1]
        nice   = st["attributes"].get("friendly_name", ent_id)

        # 1️⃣  Try full YAML (works for YAML + UI automations)
        yaml_txt = await ha_get(f"/api/config/automation/config/{slug}")
        if yaml_txt:
            try:
                yaml_obj = yaml.safe_load(yaml_txt) or {}
                entities  = collect_entities(yaml_obj)
                print(f"yaml OK   – {slug:<40} ({len(entities)} entities)")
            except yaml.YAMLError:
                entities = []
        else:
            # 2️⃣  Fall back to attributes
            entities = collect_entities(st["attributes"])
            print(f"yaml miss → {slug:<40} ({len(entities)} entities)")

        dep[ent_id] = {
            "friendly_name": nice,
            "entities": sorted(set(entities)),
        }

    print("▶ built map with", len(dep), "automations")
    return dep
