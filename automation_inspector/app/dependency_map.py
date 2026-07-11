"""Build the Automation Inspector API model from a Home Assistant snapshot."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from app import APP_VERSION
from app.automation_file import FileAutomation, scan_automations_file
from app.compatibility import inspect_compatibility
from app.ha_client import HomeAssistantClient, SourceSnapshot
from app.references import TargetUse, collect_entity_references, iter_target_uses
from app.settings import Settings

HELPER_DOMAINS = {
    "counter",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "schedule",
    "timer",
}


def _as_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {item for item in value if isinstance(item, str)}
    return set()


def _description_for(snapshot: SourceSnapshot, use: TargetUse) -> dict[str, Any] | None:
    if not use.component:
        return None
    if use.kind == "trigger":
        value = snapshot.trigger_descriptions.get(use.component)
        return value if isinstance(value, dict) else None
    if use.kind == "condition":
        value = snapshot.condition_descriptions.get(use.component)
        return value if isinstance(value, dict) else None
    if use.kind == "action" and "." in use.component:
        domain, service = use.component.split(".", 1)
        services = snapshot.service_descriptions.get(domain)
        if isinstance(services, dict):
            value = services.get(service)
            return value if isinstance(value, dict) else None
    return None


def _entity_filters(target_description: Mapping[str, Any]) -> list[dict[str, Any]]:
    filters = target_description.get("entity", [])
    if isinstance(filters, dict):
        return [filters]
    if isinstance(filters, list):
        return [item for item in filters if isinstance(item, dict)]
    return []


def _matches_target(
    *,
    entity_id: str,
    direct: bool,
    use: TargetUse,
    snapshot: SourceSnapshot,
    state_map: Mapping[str, dict[str, Any]],
    registry_map: Mapping[str, dict[str, Any]],
) -> bool:
    description = _description_for(snapshot, use)
    if description is None:
        if direct:
            return True
        component_domain = (use.component or "").split(".", 1)[0]
        entity_domain = entity_id.split(".", 1)[0]
        source_domain = str(snapshot.entity_sources.get(entity_id, {}).get("domain", ""))
        return component_domain in {entity_domain, source_domain} or not component_domain

    target_description = description.get("target")
    if not isinstance(target_description, dict):
        return direct
    entry = registry_map.get(entity_id, {})
    if (
        not direct
        and target_description.get("primary_entities_only", True)
        and entry.get("entity_category") is not None
    ):
        return False

    filters = _entity_filters(target_description)
    if not filters:
        return True
    state = state_map.get(entity_id, {})
    raw_attributes = state.get("attributes")
    attributes: dict[str, Any] = raw_attributes if isinstance(raw_attributes, dict) else {}
    entity_domain = entity_id.split(".", 1)[0]
    integration = str(snapshot.entity_sources.get(entity_id, {}).get("domain", ""))
    device_class = (
        attributes.get("device_class")
        or entry.get("device_class")
        or entry.get("original_device_class")
    )
    supported_features = attributes.get("supported_features", 0)
    try:
        supported = int(supported_features or 0)
    except (TypeError, ValueError):
        supported = 0

    for entity_filter in filters:
        filter_integration = entity_filter.get("integration")
        if filter_integration and integration != filter_integration:
            continue
        domains = _as_set(entity_filter.get("domain"))
        if domains and entity_domain not in domains:
            continue
        device_classes = _as_set(entity_filter.get("device_class"))
        if device_classes and device_class not in device_classes:
            continue
        features = entity_filter.get("supported_features", [])
        if isinstance(features, int):
            features = [features]
        if (
            isinstance(features, list)
            and features
            and not any(
                isinstance(feature, int) and feature & supported == feature for feature in features
            )
        ):
            continue
        return True
    return False


def _validation_findings(validation: Mapping[str, Any], source_key: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for section, result in validation.items():
        if not isinstance(result, dict) or result.get("valid") is not False:
            continue
        findings.append(
            {
                "code": f"invalid_{section}",
                "severity": "error",
                "path": f"$.{section}",
                "message": str(result.get("error") or f"Invalid {section}"),
                "current": None,
                "replacement": None,
                "docs_url": "https://www.home-assistant.io/docs/automation/",
                "source": source_key,
            }
        )
    return findings


def _target_findings(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    labels = {
        "missing_devices": "device",
        "missing_areas": "area",
        "missing_floors": "floor",
        "missing_labels": "label",
    }
    for target in targets:
        for field, label in labels.items():
            for missing in target.get(field, []):
                findings.append(
                    {
                        "code": "missing_target",
                        "severity": "error",
                        "path": target["path"],
                        "message": f"Referenced {label} target '{missing}' does not exist.",
                        "current": missing,
                        "replacement": None,
                        "docs_url": "https://www.home-assistant.io/docs/automation/",
                    }
                )
    return findings


def _latest_traces(traces: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for trace in traces:
        if trace.get("not_triggered"):
            continue
        item_id = trace.get("item_id")
        timestamp = trace.get("timestamp")
        if not isinstance(item_id, str) or not isinstance(timestamp, dict):
            continue
        start = str(timestamp.get("start", ""))
        previous = latest.get(item_id)
        previous_start = str((previous or {}).get("timestamp", {}).get("start", ""))
        if previous is None or start > previous_start:
            latest[item_id] = trace
    return latest


def _trace_info(
    config_id: str | None,
    latest: Mapping[str, dict[str, Any]],
    details: Mapping[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not config_id or config_id not in latest:
        return None
    summary = latest[config_id]
    template_errors: list[str] = []
    detail = details.get(config_id)
    if isinstance(detail, dict):
        steps = detail.get("trace")
        if isinstance(steps, dict):
            for elements in steps.values():
                if not isinstance(elements, list):
                    continue
                for element in elements:
                    if not isinstance(element, dict):
                        continue
                    errors = element.get("template_errors")
                    if isinstance(errors, list):
                        template_errors.extend(str(error) for error in errors)
    return {
        "run_id": summary.get("run_id"),
        "state": summary.get("state"),
        "script_execution": summary.get("script_execution"),
        "error": summary.get("error"),
        "timestamp": summary.get("timestamp"),
        "template_errors": sorted(set(template_errors)),
    }


def _dedupe_findings(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for finding in findings:
        key = (
            finding.get("code"),
            finding.get("path"),
            finding.get("current"),
            finding.get("message"),
        )
        unique[key] = finding
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        unique.values(),
        key=lambda item: (
            severity_order.get(str(item.get("severity")), 9),
            str(item.get("path", "")),
            str(item.get("code", "")),
        ),
    )


def _entity_status(
    entity_id: str,
    state_map: Mapping[str, dict[str, Any]],
    registry_map: Mapping[str, dict[str, Any]],
) -> tuple[str, str]:
    state = state_map.get(entity_id)
    if state is not None:
        value = str(state.get("state", "unknown"))
        return value, value if value in {"unavailable", "unknown"} else "ok"
    entry = registry_map.get(entity_id)
    if entry and entry.get("disabled_by") is not None:
        return "disabled", "disabled"
    return "missing", "missing"


def _target_rows(
    configs: list[tuple[str, dict[str, Any]]],
    snapshot: SourceSnapshot,
    references: dict[str, set[str]],
    state_map: Mapping[str, dict[str, Any]],
    registry_map: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for source_key, config in configs:
        for use in iter_target_uses(config):
            resolution = snapshot.target_resolutions.get(use.key, {})
            direct_entities = set(use.target.get("entity_id", []))
            resolved_entities = _as_set(resolution.get("referenced_entities"))
            primary_entities = _as_set(resolution.get("primary_entities"))
            description = _description_for(snapshot, use)
            target_description = description.get("target") if description else None
            primary_only = isinstance(target_description, dict) and target_description.get(
                "primary_entities_only", True
            )
            matched_entities: list[str] = []
            for entity_id in sorted(resolved_entities | direct_entities):
                direct = entity_id in direct_entities
                if (
                    not direct
                    and primary_only
                    and "primary_entities" in resolution
                    and entity_id not in primary_entities
                ):
                    continue
                if direct or _matches_target(
                    entity_id=entity_id,
                    direct=False,
                    use=use,
                    snapshot=snapshot,
                    state_map=state_map,
                    registry_map=registry_map,
                ):
                    references.setdefault(entity_id, set()).add(f"{use.kind}_target")
                    matched_entities.append(entity_id)
            targets.append(
                {
                    "path": use.path,
                    "kind": use.kind,
                    "component": use.component,
                    "entity_ids": matched_entities,
                    "device_ids": use.target.get("device_id", []),
                    "area_ids": use.target.get("area_id", []),
                    "floor_ids": use.target.get("floor_id", []),
                    "label_ids": use.target.get("label_id", []),
                    "dynamic_target": use.dynamic_target,
                    "runtime_resolved": bool(use.dynamic_target),
                    "missing_devices": sorted(_as_set(resolution.get("missing_devices"))),
                    "missing_areas": sorted(_as_set(resolution.get("missing_areas"))),
                    "missing_floors": sorted(_as_set(resolution.get("missing_floors"))),
                    "missing_labels": sorted(_as_set(resolution.get("missing_labels"))),
                    "source": source_key,
                }
            )
    return targets


def _analyze_automation(
    *,
    key: str,
    state: dict[str, Any] | None,
    configs: list[tuple[str, dict[str, Any]]],
    config_id: str | None,
    loaded: bool,
    snapshot: SourceSnapshot,
    state_map: Mapping[str, dict[str, Any]],
    registry_map: Mapping[str, dict[str, Any]],
    known_domains: set[str],
    latest_traces: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    attributes = state.get("attributes", {}) if state else {}
    if not isinstance(attributes, dict):
        attributes = {}
    references: dict[str, set[str]] = {}
    compatibility: list[dict[str, Any]] = []
    for source_key, config in configs:
        for entity_id, sources in collect_entity_references(config, known_domains).items():
            references.setdefault(entity_id, set()).update(sources)
        compatibility.extend(inspect_compatibility(config))
        compatibility.extend(
            _validation_findings(snapshot.validations.get(source_key, {}), source_key)
        )

    targets = _target_rows(configs, snapshot, references, state_map, registry_map)
    compatibility.extend(_target_findings(targets))
    compatibility = _dedupe_findings(compatibility)

    entities: list[dict[str, Any]] = []
    for entity_id in sorted(references):
        entity_state = state_map.get(entity_id, {})
        entity_attributes = entity_state.get("attributes", {})
        if not isinstance(entity_attributes, dict):
            entity_attributes = {}
        registry = registry_map.get(entity_id, {})
        value, status = _entity_status(entity_id, state_map, registry_map)
        entities.append(
            {
                "id": entity_id,
                "domain": entity_id.split(".", 1)[0],
                "name": (
                    entity_attributes.get("friendly_name")
                    or registry.get("name")
                    or registry.get("original_name")
                    or entity_id
                ),
                "state": value,
                "status": status,
                "ok": status == "ok",
                "sources": sorted(references[entity_id]),
                "device_id": registry.get("device_id"),
                "area_id": registry.get("area_id"),
            }
        )

    trace = _trace_info(config_id, latest_traces, snapshot.trace_details)
    trace_is_issue = bool(
        trace
        and (
            trace.get("error")
            or trace.get("template_errors")
            or trace.get("script_execution") in {"error", "failed_max_runs"}
        )
    )
    bad_entities = sum(1 for entity in entities if not entity["ok"])
    compatibility_errors = sum(
        1 for finding in compatibility if finding["severity"] in {"error", "warning"}
    )
    if not loaded:
        status = "not_loaded"
    elif state is not None and str(state.get("state")) == "on":
        status = "enabled"
    elif state is not None and str(state.get("state")) == "unavailable":
        status = "unavailable"
    else:
        status = "disabled"

    primary_config = configs[0][1] if configs else {}
    warnings: list[str] = []
    if loaded and key in snapshot.automation_config_errors:
        warnings.append(snapshot.automation_config_errors[key])
    if "use_blueprint" in primary_config:
        warnings.append("Blueprint analysis is limited to its configured inputs.")

    friendly_name = (
        attributes.get("friendly_name") or primary_config.get("alias") or config_id or key
    )
    return {
        "entity_id": key if loaded else None,
        "friendly_name": friendly_name,
        "enabled": status == "enabled",
        "loaded": loaded,
        "status": status,
        "config_id": config_id,
        "last_triggered": attributes.get("last_triggered"),
        "mode": primary_config.get("mode"),
        "source": "runtime" if loaded else "automations_file",
        "entities": entities,
        "targets": targets,
        "compatibility_issues": compatibility,
        "trace": trace,
        "warnings": warnings,
        "issue_count": bad_entities + compatibility_errors + int(trace_is_issue) + int(not loaded),
    }


def _claim_file_automation(
    config_id: str | None,
    runtime_config: dict[str, Any] | None,
    file_by_id: Mapping[str, list[FileAutomation]],
    matched_file_keys: set[str],
) -> FileAutomation | None:
    """Match at most one file entry to one runtime automation."""
    if not config_id:
        return None
    candidates = [
        automation
        for automation in file_by_id.get(config_id, [])
        if automation.key not in matched_file_keys
    ]
    if not candidates:
        return None
    if runtime_config is not None:
        for candidate in candidates:
            if candidate.config == runtime_config:
                return candidate
    return candidates[0]


def build_inspection(snapshot: SourceSnapshot, settings: Settings) -> dict[str, Any]:
    """Convert raw Home Assistant data into the versioned public API model."""
    started = time.perf_counter()
    state_map = {
        str(state["entity_id"]): state
        for state in snapshot.states
        if isinstance(state.get("entity_id"), str)
    }
    registry_map = {
        str(entry["entity_id"]): entry
        for entry in snapshot.entity_registry
        if isinstance(entry.get("entity_id"), str)
    }
    known_domains = {
        entity_id.split(".", 1)[0]
        for entity_id in set(state_map) | set(registry_map)
        if "." in entity_id
    }
    file_by_id: dict[str, list[FileAutomation]] = {}
    for automation in snapshot.file_automations:
        if automation.config_id:
            file_by_id.setdefault(automation.config_id, []).append(automation)

    latest_traces = _latest_traces(snapshot.traces)
    automations: dict[str, dict[str, Any]] = {}
    matched_file_keys: set[str] = set()
    for entity_id, state in sorted(state_map.items()):
        if not entity_id.startswith("automation."):
            continue
        attributes = state.get("attributes", {})
        if not isinstance(attributes, dict):
            attributes = {}
        raw_config_id = attributes.get("id")
        config_id = str(raw_config_id) if raw_config_id is not None else None
        runtime_config = snapshot.automation_configs.get(entity_id)
        file_automation = _claim_file_automation(
            config_id, runtime_config, file_by_id, matched_file_keys
        )
        if file_automation:
            matched_file_keys.add(file_automation.key)
        if not settings.include_disabled and state.get("state") != "on":
            continue

        configs: list[tuple[str, dict[str, Any]]] = []
        if runtime_config:
            configs.append((f"runtime:{entity_id}", runtime_config))
        elif file_automation:
            configs.append((file_automation.key, file_automation.config))
        if not configs:
            configs.append((f"attributes:{entity_id}", attributes))
        automations[entity_id] = _analyze_automation(
            key=entity_id,
            state=state,
            configs=configs,
            config_id=config_id,
            loaded=True,
            snapshot=snapshot,
            state_map=state_map,
            registry_map=registry_map,
            known_domains=known_domains,
            latest_traces=latest_traces,
        )

    for file_automation in snapshot.file_automations:
        if file_automation.key in matched_file_keys:
            continue
        key = f"unloaded:{file_automation.config_id or file_automation.index}"
        if key in automations:
            key = f"{key}:{file_automation.index}"
        automations[key] = _analyze_automation(
            key=key,
            state=None,
            configs=[(file_automation.key, file_automation.config)],
            config_id=file_automation.config_id,
            loaded=False,
            snapshot=snapshot,
            state_map=state_map,
            registry_map=registry_map,
            known_domains=known_domains,
            latest_traces=latest_traces,
        )

    all_referenced = {
        entity["id"] for automation in automations.values() for entity in automation["entities"]
    }
    unreferenced_helpers = []
    for entity_id in sorted(set(state_map) | set(registry_map)):
        if entity_id.split(".", 1)[0] not in HELPER_DOMAINS or entity_id in all_referenced:
            continue
        state = state_map.get(entity_id, {})
        attributes = state.get("attributes", {})
        if not isinstance(attributes, dict):
            attributes = {}
        registry = registry_map.get(entity_id, {})
        value, status = _entity_status(entity_id, state_map, registry_map)
        unreferenced_helpers.append(
            {
                "id": entity_id,
                "name": (
                    attributes.get("friendly_name")
                    or registry.get("name")
                    or registry.get("original_name")
                    or entity_id
                ),
                "state": value,
                "status": status,
            }
        )

    entity_rows = [
        entity for automation in automations.values() for entity in automation["entities"]
    ]
    compatibility_rows = [
        finding
        for automation in automations.values()
        for finding in automation["compatibility_issues"]
        if finding["severity"] in {"error", "warning"}
    ]
    unresolved_targets = sum(
        len(target[field])
        for automation in automations.values()
        for target in automation["targets"]
        for field in (
            "missing_devices",
            "missing_areas",
            "missing_floors",
            "missing_labels",
        )
    )
    trace_failures = sum(
        1
        for automation in automations.values()
        if automation["trace"]
        and (
            automation["trace"].get("error")
            or automation["trace"].get("template_errors")
            or automation["trace"].get("script_execution") in {"error", "failed_max_runs"}
        )
    )
    ha_config = snapshot.home_assistant_config
    return {
        "schema_version": 2,
        "app_version": APP_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "home_assistant": {
            "version": ha_config.get("version"),
            "location_name": ha_config.get("location_name"),
            "frontend_url": ha_config.get("external_url") or ha_config.get("internal_url"),
        },
        "summary": {
            "automations": len(automations),
            "enabled": sum(1 for item in automations.values() if item["enabled"]),
            "disabled": sum(1 for item in automations.values() if item["status"] == "disabled"),
            "unloaded": sum(1 for item in automations.values() if not item["loaded"]),
            "dependency_references": len(entity_rows),
            "unique_entities": len({row["id"] for row in entity_rows}),
            "missing_entities": sum(1 for row in entity_rows if row["status"] == "missing"),
            "unavailable_entities": sum(1 for row in entity_rows if row["status"] == "unavailable"),
            "unknown_entities": sum(1 for row in entity_rows if row["status"] == "unknown"),
            "disabled_entities": sum(1 for row in entity_rows if row["status"] == "disabled"),
            "automations_with_issues": sum(
                1 for item in automations.values() if item["issue_count"] > 0
            ),
            "compatibility_issues": len(compatibility_rows),
            "unresolved_targets": unresolved_targets,
            "trace_failures": trace_failures,
            "unreferenced_helpers": len(unreferenced_helpers),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
        "automations": automations,
        "unreferenced_helpers": unreferenced_helpers,
        "orphans": [helper["id"] for helper in unreferenced_helpers],
        "warnings": snapshot.warnings,
    }


class DependencyMapBuilder:
    """Orchestrate file scanning, Home Assistant retrieval, and analysis."""

    def __init__(self, settings: Settings, client: HomeAssistantClient | None = None) -> None:
        self.settings = settings
        self.client = client or HomeAssistantClient(settings)

    async def build(self) -> dict[str, Any]:
        file_scan = await scan_automations_file(
            self.settings.automations_file, self.settings.scan_automations_file
        )
        snapshot = await self.client.fetch_snapshot(file_scan.automations)
        snapshot.warnings.extend(file_scan.warnings)
        return build_inspection(snapshot, self.settings)


async def build_map() -> dict[str, Any]:
    """Compatibility entry point for legacy imports."""
    settings = Settings.load()
    return await DependencyMapBuilder(settings).build()


build_dependency_map = build_map
