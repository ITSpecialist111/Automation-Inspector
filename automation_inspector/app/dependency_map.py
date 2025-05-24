"""
dependency_map.py – builds the JSON served at /dependency_map.json

Adds:
• generated_at ISO timestamp
• entity last_changed secondsAgo (for “stale” highlighting)
• link to editor (numeric id) or developer-tools fallback
"""

from __future__ import annotations
import logging, os, re, time
from datetime import datetime, timezone
from typing import Any, List

import httpx
_LOGGER = logging.getLogger(__name__)

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
async def ha_get(path:str)->Any:
    global http
    if http is None:
        http = httpx.AsyncClient(
            base_url=SUPERVISOR,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=20,
        )
    r=await http.get(path); r.raise_for_status(); return r.json()

def collect_entities(obj:Any)->List[str]:
    found:set[str]=set()
    if isinstance(obj,str):
        found.update(ENTITY_RE.findall(obj))
    elif isinstance(obj,list):
        for itm in obj: found.update(collect_entities(itm))
    elif isinstance(obj,dict):
        for v in obj.values(): found.update(collect_entities(v))
    return list(found)

# ───────────────────────── builder ─────────────────────────
async def build_map()->dict[str,Any]:
    gen_ts = datetime.now(timezone.utc)
    states = await ha_get("/states")
    state_map = {s["entity_id"]: s for s in states}

    autos = [s for s in states if s["entity_id"].startswith("automation.")]
    all_entities=set(state_map)

    # group offline cache
    offline_by_group={}
    for s in states:
        if s["entity_id"].startswith("group."):
            mem=s["attributes"].get("entity_id",[])
            off=[m for m in mem if state_map.get(m,{}).get("state") in ("unavailable","unknown")]
            if off: offline_by_group[s["entity_id"]]=off

    summary=dict(total=len(autos),unknown=0,offline=0,stale=0)
    dep={}

    for a in autos:
        aid=a["entity_id"]; num=a["attributes"].get("id")
        # fetch config if numeric id
        conf={}
        try:
            if str(num).isdigit():
                conf=await ha_get(f"/config/automation/config/{num}")
        except Exception as e: _LOGGER.debug("cfg fallback %s: %s",aid,e)
        if not conf:
            conf=dict(trigger=a["attributes"].get("trigger",[]),
                      condition=a["attributes"].get("condition",[]),
                      action=a["attributes"].get("action",[]))
        ents=collect_entities(conf)

        # unknown
        unknown=[eid for trig in conf.get("trigger",[])
                 if isinstance(trig,dict)
                 for eid in (trig.get("entity_id") or ([]))
                    if isinstance(eid,str) and eid not in all_entities]
        summary["unknown"]+=bool(unknown)

        # stale
        last=a["attributes"].get("last_triggered")
        stale=None
        if last: stale=(gen_ts-datetime.fromisoformat(last)).days
        summary["stale"]+= stale is not None and stale>=STALE_DAYS

        # offline members
        off=[]
        for g in [e for e in ents if e.startswith("group.")]:
            off+=offline_by_group.get(g,[])
        summary["offline"]+=bool(off)

        rows=[]
        for eid in ents:
            st=state_map.get(eid,{})
            changed=datetime.fromisoformat(st.get("last_changed",gen_ts.isoformat()))
            age=int((gen_ts-changed).total_seconds())
            rows.append(dict(
                id=eid,
                state=st.get("state","—"),
                unit=st.get("attributes",{}).get("unit_of_measurement",""),
                friendly=st.get("attributes",{}).get("friendly_name",""),
                age=age,
            ))

        dep[aid]=dict(
            friendly_name=a["attributes"].get("friendly_name",aid),
            ui_link=f"/config/automation/edit/{num}" if str(num).isdigit()
                    else f"/developer-tools/state?history_back=1&entity_id={aid}",
            entities=rows,
            unknown_triggers=unknown,
            offline_members=off,
            last_triggered=last,
            stale_days=stale,
            stale_threshold=STALE_DAYS,
        )

    dep["_summary"]=summary|dict(generated_at=gen_ts.isoformat())
    return dep
