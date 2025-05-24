"""
dependency_map.py – builds the JSON served at /dependency_map.json
Implements:
 • entity extraction
 • unknown / broken trigger detection
 • stale-automation flag
 • offline group-member detection
"""

from __future__ import annotations

import asyncio, os, re, logging
from datetime import datetime, timezone
from time import time
from typing import Any, List

import httpx

_LOGGER = logging.getLogger(__name__)

# ──────────────────────────────── constants ──────────────────────────────────
ENTITY_RE = re.compile(
    r"\b("
    r"alarm_control_panel|automation|binary_sensor|button|calendar|camera|climate|"
    r"cover|device_tracker|fan|group|humidifier|input_boolean|input_button|"
    r"input_datetime|input_number|input_select|input_text|light|lock|media_player|"
    r"number|person|remote|scene|script|select|sensor|switch|timer|vacuum|"
    r"water_heater|weather|zone"
    r")\.[\w\-_]+\b",
    re.I,
)

SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN")
SUPERVISOR_URL   = "http://supervisor/core/api"
STALE_DAYS       = int(os.getenv("INSPECTOR_STALE_DAYS", "30"))

client: httpx.AsyncClient | None = None


# ──────────────────────────────── helpers ─────────────────────────────────────
async def ha_get(path: str) -> Any:
    """Minimal wrapper around the supervisor proxy API."""
    global client
    if client is None:
        client = httpx.AsyncClient(
            base_url=SUPERVISOR_URL,
            headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
            timeout=15,
        )
    r = await client.get(path)
    r.raise_for_status()
    return r.json()


def collect_entities(obj: Any) -> List[str]:
    """Recursively pull entity_ids out of a Home-Assistant automation structure."""
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


# ──────────────────────────────── builder ─────────────────────────────────────
async def build_map() -> dict[str, Any]:
    """Return the full dependency-map used by /dependency_map.json."""
    automations = await ha_get("/states/automation")
    states      = await ha_get("/states")
    all_entities = {s["entity_id"] for s in states}

    now_utc   = datetime.now(timezone.utc)
    state_map = {s["entity_id"]: s for s in states}

    # Pre-compute offline members for every group.*
    offline_by_group: dict[str, List[str]] = {}
    for st in states:
        if st["entity_id"].startswith("group."):
            members = st["attributes"].get("entity_id", [])
            offline = [
                m for m in members
                if state_map.get(m, {}).get("state") in ("unavailable", "unknown")
            ]
            if offline:
                offline_by_group[st["entity_id"]] = offline

    dep_map: dict[str, Any] = {}

    for auto in automations:
        auto_id  = auto["entity_id"]
        config   = await ha_get(f"/services/automation/get_config?entity_id={auto_id}")
        entities = collect_entities(config)

        # ---------- unknown / broken triggers ---------------------------------
        unknown: list[str] = []
        for trig in config.get("trigger", []):
            if isinstance(trig, dict):
                ids = trig.get("entity_id") or []
                if isinstance(ids, str):
                    ids = [ids]
                for eid in ids:
                    if eid not in all_entities:
                        unknown.append(eid)
        # ----------------------------------------------------------------------

        # ---------- stale calculation -----------------------------------------
        last = auto["attributes"].get("last_triggered")
        stale_days = None
        if last:
            delta      = now_utc - datetime.fromisoformat(last)
            stale_days = delta.days
        # ----------------------------------------------------------------------

        # ---------- offline members in referenced groups ----------------------
        offline_members: list[str] = []
        for e in entities:
            if e.startswith("group.") and e in offline_by_group:
                offline_members.extend(offline_by_group[e])
        # ----------------------------------------------------------------------

        dep_map[auto_id] = {
            "friendly_name": auto["attributes"].get("friendly_name", auto_id),
            "entities":         sorted(entities),
            "unknown_triggers": sorted(set(unknown)),
            "offline_members":  sorted(set(offline_members)),
            "last_triggered":   last,
            "stale_days":       stale_days,
            "stale_threshold":  STALE_DAYS,
        }

    return dep_map
