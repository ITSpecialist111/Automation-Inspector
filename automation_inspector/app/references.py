"""Extract direct entity references and Home Assistant target selections."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

ENTITY_ID_RE = re.compile(r"(?<![a-z0-9_])([a-z_][a-z0-9_]*\.[a-z0-9_]+)(?![a-z0-9_.])")
TEMPLATE_ENTITY_RE = re.compile(
    r"(?:states|is_state|is_state_attr|state_attr|expand)\s*\(\s*['\"]"
    r"([a-z_][a-z0-9_]*\.[a-z0-9_]+)['\"]"
)

TARGET_KEYS = ("entity_id", "device_id", "area_id", "floor_id", "label_id")
COMPONENT_KEYS = {"trigger", "platform", "condition", "action", "service"}
ENTITY_VALUE_KEYS = {
    "entity_id",
    "entity",
    "zone",
    "at",
    "above",
    "below",
    "temperature_entity_id",
    "humidity_entity_id",
}

STANDARD_DOMAINS = frozenset(
    {
        "air_quality",
        "alarm_control_panel",
        "assist_satellite",
        "automation",
        "binary_sensor",
        "button",
        "calendar",
        "camera",
        "climate",
        "conversation",
        "counter",
        "cover",
        "date",
        "datetime",
        "device_tracker",
        "event",
        "fan",
        "group",
        "humidifier",
        "image",
        "input_boolean",
        "input_button",
        "input_datetime",
        "input_number",
        "input_select",
        "input_text",
        "lawn_mower",
        "light",
        "lock",
        "media_player",
        "notify",
        "number",
        "person",
        "remote",
        "scene",
        "schedule",
        "script",
        "select",
        "sensor",
        "siren",
        "sun",
        "switch",
        "text",
        "time",
        "timer",
        "todo",
        "update",
        "vacuum",
        "valve",
        "water_heater",
        "weather",
        "zone",
    }
)


def _as_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if isinstance(item, str)]
    return []


def normalize_target(value: Any) -> dict[str, list[str]]:
    """Normalize a target to sorted lists accepted by the WebSocket API."""
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key in TARGET_KEYS:
        values = sorted(set(_as_strings(value.get(key))))
        if values:
            normalized[key] = values
    return normalized


def target_key(target: dict[str, list[str]]) -> str:
    return json.dumps(target, sort_keys=True, separators=(",", ":"))


def _is_template(value: str) -> bool:
    return any(marker in value for marker in ("{{", "{%", "{#"))


def _partition_target(
    target: dict[str, list[str]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    static: dict[str, list[str]] = {}
    dynamic: dict[str, list[str]] = {}
    for key, values in target.items():
        static_values = [value for value in values if not _is_template(value)]
        dynamic_values = [value for value in values if _is_template(value)]
        if static_values:
            static[key] = static_values
        if dynamic_values:
            dynamic[key] = dynamic_values
    return static, dynamic


@dataclass(frozen=True, slots=True)
class TargetUse:
    path: str
    kind: str
    component: str | None
    target: dict[str, list[str]]
    dynamic_target: dict[str, list[str]]

    @property
    def key(self) -> str:
        return target_key(self.target)


def iter_target_uses(config: dict[str, Any]) -> list[TargetUse]:
    """Find targets and the trigger, condition, or action that owns each target."""
    uses: list[TargetUse] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
            return
        if not isinstance(value, dict):
            return

        normalized_target = normalize_target(value.get("target"))
        target, dynamic_target = _partition_target(normalized_target)
        if target or dynamic_target:
            if isinstance(value.get("trigger", value.get("platform")), str):
                kind = "trigger"
                component = str(value.get("trigger", value.get("platform")))
            elif isinstance(value.get("condition"), str):
                kind = "condition"
                component = str(value["condition"])
            elif isinstance(value.get("action", value.get("service")), str):
                kind = "action"
                component = str(value.get("action", value.get("service")))
            else:
                kind = "target"
                component = None
            uses.append(TargetUse(f"{path}.target", kind, component, target, dynamic_target))

        for key, child in value.items():
            if key != "target":
                walk(child, f"{path}.{key}")

    walk(config, "$")
    return uses


def collect_entity_references(
    config: dict[str, Any], known_domains: Iterable[str]
) -> dict[str, set[str]]:
    """Extract explicit and templated entity IDs while excluding service/component names."""
    domains = set(known_domains) | set(STANDARD_DOMAINS)
    references: dict[str, set[str]] = {}

    def add(entity_id: str, source: str) -> None:
        references.setdefault(entity_id, set()).add(source)

    def scan_string(value: str, key: str | None) -> None:
        exact = ENTITY_ID_RE.fullmatch(value.strip())
        if exact and key in COMPONENT_KEYS:
            return
        template_matches = set(TEMPLATE_ENTITY_RE.findall(value))
        for entity_id in template_matches:
            add(entity_id, "template")
        explicit_key = key in ENTITY_VALUE_KEYS
        source = "template" if "{{" in value or "{%" in value else "configuration"
        for entity_id in ENTITY_ID_RE.findall(value):
            domain = entity_id.split(".", 1)[0]
            if explicit_key or entity_id in template_matches or domain in domains:
                add(entity_id, "explicit" if explicit_key else source)

    def walk(value: Any, key: str | None = None) -> None:
        if isinstance(value, str):
            scan_string(value, key)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, key)
            return
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))

    walk(config)
    for target in iter_target_uses(config):
        for entity_id in target.target.get("entity_id", []):
            add(entity_id, f"{target.kind}_target")
    return references
