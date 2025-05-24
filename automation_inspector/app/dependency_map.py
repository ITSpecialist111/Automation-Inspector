"""
dependency_map.py – builds the JSON served at /dependency_map.json
Adds:
 • entity state lookup
 • top-level summary counts
 • numeric-id check to avoid 404 on YAML automations
"""

from __future__ import annotations

import logging, os, re
from datetime import datetime, timezone
from typing import Any, List

import httpx

_LOGGER = logging.getLogger(__name__)

# ───────────────────────── constants ─────────────────────────
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

SUPERVISOR = "http://supervisor/core/api"
TOKEN      = os.environ["SUPERVISOR_TOKEN"]
STALE_DAYS = int(os.getenv("INSPECTOR_STALE_DAYS", "30"))

http: httpx.AsyncClient | None = None


# ───────────────────────── helpers ───────────────────────────
async def ha_get(path: str) -> Any:
    global http
    if http is None:
        http = httpx.AsyncClient(
            base_url=SUPERVISOR, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=20
        )
    r = await http.get(path)
    r.raise_for_status()
    return r.json()


def collect_entities(obj: Any) -> List[str]:
    found: set[str] = set()
    if isinstance(obj, str):
        found.update(ENTITY_RE.findall(obj))
    elif isinstance(obj, list):
        for itm in obj:
            found.update(collect_entities(itm))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.update(collect_entities(v))
    return list(found)


# ───────────────────────── builder ───────────────────────────
async def build_map() -> dict[str, Any]:
    states = await ha_get("/states")
    state_map = {s["entity_id"]: s for s in states}

    automations = [s for s in states if s["entity_id"].startswith("automation.")]
    all_entities = set(state_map)

    now_utc = datetime.now(timezone.utc)

    offline_by_group: dict[str, List[str]] = {}
    for st in states:
        if st["entity_id"].startswith("group."):
            members = st["attributes"].get("entity_id", [])
            offline = [
                m
                for m in members
                if state_map.get(m, {}).get("state") in ("unavailable", "unknown")
            ]
            if offline:
                offline_by_group[st["entity_id"]] = offline

    dep_map: dict[str, Any] = {}
    # counters for summary
    total_unknown = total_offline = total_stale = 0

    for auto in automations:
        auto_id = auto["entity_id"]
        num_id  = auto["attributes"].get("id")
        is_numeric_id = isinstance(num_id, (int, str)) and str(num_id).isdigit()

        # ─ fetch config ─
        try:
            if is_numeric_id:
                config = await ha_get(f"/config/automation/config/{num_id}")
            else:
                config = {
                    "trigger":   auto["attributes"].get("trigger", []),
                    "condition": auto["attributes"].get("condition", []),
                    "action":    auto["attributes"].get("action", []),
                }
        except Exception as exc:
            _LOGGER.warning("Cannot fetch config for %s: %s", auto_id, exc)
            config = {
                "trigger":   auto["attributes"].get("trigger", []),
                "condition": auto["attributes"].get("condition", []),
                "action":    auto["attributes"].get("action", []),
            }

        entities = collect_entities(config)

        # unknown triggers
        unknown: list[str] = []
        for trig in config.get("trigger", []):
            if isinstance(trig, dict):
                ids = trig.get("entity_id") or []
                ids = [ids] if isinstance(ids, str) else ids
                unknown.extend(eid for eid in ids if eid not in all_entities)
        total_unknown += bool(unknown)

        # stale calc
        last = auto["attributes"].get("last_triggered")
        stale = None
        if last:
            stale = (now_utc - datetime.fromisoformat(last)).days
        total_stale += stale is not None and stale >= STALE_DAYS

        # offline members
        offline_members: list[str] = []
        for e in entities:
            if e.startswith("group.") and e in offline_by_group:
                offline_members.extend(offline_by_group[e])
        total_offline += bool(offline_members)

        # bundle entity display data (id + state)
        entity_rows = [
            {
                "id": eid,
                "state": state_map.get(eid, {}).get("state", "—"),
            }
            for eid in entities
        ]

        dep_map[auto_id] = {
            "friendly_name": auto["attributes"].get("friendly_name", auto_id),
            "entities": entity_rows,
            "unknown_triggers": sorted(set(unknown)),
            "offline_members":  sorted(set(offline_members)),
            "last_triggered":   last,
            "stale_days":       stale,
            "stale_threshold":  STALE_DAYS,
        }

    dep_map["_summary"] = {
        "total": len(automations),
        "unknown": total_unknown,
        "offline": total_offline,
        "stale": total_stale,
    }
    return dep_map
