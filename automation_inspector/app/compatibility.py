"""Static compatibility checks for modern Home Assistant automation syntax."""

from __future__ import annotations

from typing import Any

RELEASE_NOTES_URL = (
    "https://www.home-assistant.io/blog/2026/07/01/release-20267/#backward-incompatible-changes"
)

TRIGGER_RENAMES = {
    "battery.low": "battery.became_low",
    "battery.not_low": "battery.no_longer_low",
    "lawn_mower.docked": "lawn_mower.returned_to_dock",
    "schedule.turned_off": "schedule.block_ended",
    "schedule.turned_on": "schedule.block_started",
    "timer.time_remaining": "timer.remaining_time_reached",
    "update.update_became_available": "update.became_available",
    "vacuum.docked": "vacuum.returned_to_dock",
}

CONDITION_RENAMES = {
    "climate.target_humidity": "climate.is_target_humidity",
    "climate.target_temperature": "climate.is_target_temperature",
}


def _path(parent: str, key: str | int) -> str:
    return f"{parent}[{key}]" if isinstance(key, int) else f"{parent}.{key}"


def inspect_compatibility(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return actionable compatibility findings for one automation config."""
    findings: list[dict[str, Any]] = []

    def add(
        *,
        code: str,
        severity: str,
        path: str,
        message: str,
        current: str | None = None,
        replacement: str | None = None,
        docs_url: str | None = None,
    ) -> None:
        findings.append(
            {
                "code": code,
                "severity": severity,
                "path": path,
                "message": message,
                "current": current,
                "replacement": replacement,
                "docs_url": docs_url,
            }
        )

    def walk(value: Any, current_path: str) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, _path(current_path, index))
            return
        if not isinstance(value, dict):
            return

        trigger_value = value.get("trigger", value.get("platform"))
        if isinstance(trigger_value, str) and trigger_value in TRIGGER_RENAMES:
            replacement = TRIGGER_RENAMES[trigger_value]
            key = "trigger" if "trigger" in value else "platform"
            add(
                code="ha_2026_7_trigger_renamed",
                severity="error",
                path=_path(current_path, key),
                message=(
                    f"Home Assistant 2026.7 removed trigger '{trigger_value}'; use '{replacement}'."
                ),
                current=trigger_value,
                replacement=replacement,
                docs_url=RELEASE_NOTES_URL,
            )

        condition_value = value.get("condition")
        if isinstance(condition_value, str) and condition_value in CONDITION_RENAMES:
            replacement = CONDITION_RENAMES[condition_value]
            add(
                code="ha_2026_7_condition_renamed",
                severity="error",
                path=_path(current_path, "condition"),
                message=(
                    f"Home Assistant 2026.7 removed condition '{condition_value}'; "
                    f"use '{replacement}'."
                ),
                current=condition_value,
                replacement=replacement,
                docs_url=RELEASE_NOTES_URL,
            )

        options = value.get("options")
        if (
            isinstance(trigger_value, str)
            and isinstance(value.get("target"), dict)
            and isinstance(options, dict)
            and options.get("behavior") in {"any", "last"}
        ):
            current = str(options["behavior"])
            replacement = "each" if current == "any" else "all"
            add(
                code="deprecated_target_behavior",
                severity="warning",
                path=_path(_path(current_path, "options"), "behavior"),
                message=(f"Target behavior '{current}' is deprecated; use '{replacement}'."),
                current=current,
                replacement=replacement,
                docs_url="https://www.home-assistant.io/docs/automation/trigger/",
            )

        if "platform" in value and isinstance(value.get("platform"), str):
            add(
                code="legacy_trigger_platform_key",
                severity="info",
                path=_path(current_path, "platform"),
                message="Use the modern 'trigger' key instead of 'platform'.",
                current="platform",
                replacement="trigger",
                docs_url="https://www.home-assistant.io/docs/automation/trigger/",
            )

        if "service" in value and isinstance(value.get("service"), str):
            add(
                code="legacy_service_action_key",
                severity="info",
                path=_path(current_path, "service"),
                message="Use the modern 'action' key instead of 'service'.",
                current="service",
                replacement="action",
                docs_url="https://www.home-assistant.io/docs/automation/action/",
            )

        for key, child in value.items():
            walk(child, _path(current_path, str(key)))

    for singular, plural in (
        ("trigger", "triggers"),
        ("condition", "conditions"),
        ("action", "actions"),
    ):
        if singular in config and plural not in config:
            add(
                code="legacy_top_level_key",
                severity="info",
                path=f"$.{singular}",
                message=f"Use the modern top-level '{plural}' key.",
                current=singular,
                replacement=plural,
                docs_url="https://www.home-assistant.io/docs/automation/yaml/",
            )

    walk(config, "$")
    unique: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    for finding in findings:
        unique[(finding["code"], finding["path"], finding["current"])] = finding
    return list(unique.values())
