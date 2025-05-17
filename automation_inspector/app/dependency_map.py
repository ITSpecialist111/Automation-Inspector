import re
from typing import Dict, List
import httpx
import os
import asyncio

HA_URL = "http://supervisor/core"          # ← proxy root (NO /api here)
TOKEN  = os.getenv("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

ENTITY_REGEX = re.compile(r"\b(?:sensor|binary_sensor|switch|input_\w+|number)\.[\w\d_]+")

async def fetch_states() -> List[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HA_URL}/api/states", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()

async def fetch_automations() -> List[dict]:
    states = await fetch_states()
    return [s for s in states if s["entity_id"].startswith("automation.")]

def extract_entities(yaml_str: str) -> List[str]:
    return sorted(set(ENTITY_REGEX.findall(yaml_str or "")))

async def build_map() -> Dict[str, dict]:
    automations = await fetch_automations()
    dep_map = {}
    for auto in automations:
        friendly = auto["attributes"].get("friendly_name", auto["entity_id"])
        yaml_cfg = auto["attributes"].get("last_triggered_cfg") or auto["attributes"].get("source") or ""
        entities = extract_entities(yaml_cfg)
        dep_map[auto["entity_id"]] = {
            "friendly_name": friendly,
            "entities": entities,
        }
    return dep_map
async def fetch_states():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{HA_URL}/api/states", headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            print("❌ HA API error:", e.response.status_code, e.response.text[:100])
            return []