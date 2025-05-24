"""
dependency_map.py – builds /dependency_map.json

• FIX: regex now returns full entity_id (sensor.kitchen not just “sensor”)
• adds unit_of_measurement & friendly_name for UI
• summary counters per alert category
"""

from __future__ import annotations
import logging, os, re
from datetime import datetime, timezone
from typing import Any, List

import httpx
_LOGGER = logging.getLogger(__name__)

# full entity_id capture
_DOMAINS = (
    "alarm_control_panel|automation|binary_sensor|button|calendar|camera|climate|"
    "cover|device_tracker|fan|group|humidifier|input_boolean|input_button|"
    "input_datetime|input_number|input_select|input_text|light|lock|media_player|"
    "number|person|remote|scene|script|select|sensor|switch|timer|vacuum|"
    "water_heater|weather|zone"
)
ENTITY_RE = re.compile(rf"\b((?:{_DOMAINS})\.[\w\-]+)\b", re.I)

SUPERVISOR = "http://supervisor/core/api"
TOKEN      = os.environ["SUPERVISOR_TOKEN"]
STALE_DAYS = int(os.getenv("INSPECTOR_STALE_DAYS", "30"))
http: httpx.AsyncClient | None = None

async def ha_get(path: str) -> Any:
    global http
    if http is None:
        http = httpx.AsyncClient(
            base_url=SUPERVISOR,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=20,
        )
    r = await http.get(path)
    r.raise_for_status()
    return r.json()

def collect_entities(obj: Any) -> List[str]:
    found: set[str] = set()
    if isinstance(obj, str):
        found.update(ENTITY_RE.findall(obj))
    elif isinstance(obj, list):
        for itm in obj: found.update(collect_entities(itm))
    elif isinstance(obj, dict):
        for v in obj.values(): found.update(collect_entities(v))
    return list(found)

# ─────────────────────────────────────────────────────────────────────
async def build_map() -> dict[str, Any]:
    states = await ha_get("/states")
    state_map = {s["entity_id"]: s for s in states}
    automations = [s for s in states if s["entity_id"].startswith("automation.")]
    all_entities = set(state_map)

    now_utc = datetime.now(timezone.utc)

    # offline members lookup
    offline_by_group: dict[str, List[str]] = {}
    for st in states:
        if st["entity_id"].startswith("group."):
            members = st["attributes"].get("entity_id", [])
            offline = [
                m for m in members
                if state_map.get(m, {}).get("state") in ("unavailable", "unknown")
            ]
            if offline: offline_by_group[st["entity_id"]] = offline

    summary = dict(total=len(automations), unknown=0, offline=0, stale=0)
    dep_map: dict[str, Any] = {}

    for auto in automations:
        auto_id = auto["entity_id"]
        num_id  = auto["attributes"].get("id")
        config  = {}
        try:
            if str(num_id).isdigit():
                config = await ha_get(f"/config/automation/config/{num_id}")
        except Exception as e:
            _LOGGER.debug("Using attribute fallback for %s (%s)", auto_id, e)
        finally:
            if not config:
                config = {
                    "trigger":   auto["attributes"].get("trigger", []),
                    "condition": auto["attributes"].get("condition", []),
                    "action":    auto["attributes"].get("action", []),
                }

        entities = collect_entities(config)

        # ---- unknown triggers
        unknown = []
        for trig in config.get("trigger", []):
            if isinstance(trig, dict):
                ids = trig.get("entity_id") or []
                if isinstance(ids, str): ids=[ids]
                unknown += [eid for eid in ids if eid not in all_entities]
        summary["unknown"] += bool(unknown)

        # ---- stale
        last = auto["attributes"].get("last_triggered")
        stale_days = None
        if last:
            stale_days = (now_utc - datetime.fromisoformat(last)).days
        summary["stale"] += stale_days is not None and stale_days >= STALE_DAYS

        # ---- offline members
        offline_members=[]
        for g in (e for e in entities if e.startswith("group.")):
            offline_members+=offline_by_group.get(g,[])
        summary["offline"] += bool(offline_members)

        # ---- entity display rows
        rows=[]
        for eid in entities:
            st = state_map.get(eid, {})
            rows.append({
                "id": eid,
                "state": st.get("state", "—"),
                "unit": st.get("attributes", {}).get("unit_of_measurement",""),
                "friendly": st.get("attributes", {}).get("friendly_name",""),
            })

        dep_map[auto_id]={
            "friendly_name": auto["attributes"].get("friendly_name", auto_id),
            "entities": rows,
            "unknown_triggers": sorted(set(unknown)),
            "offline_members": sorted(set(offline_members)),
            "last_triggered": last,
            "stale_days": stale_days,
            "stale_threshold": STALE_DAYS,
        }

    dep_map["_summary"]=summary
    return dep_map
