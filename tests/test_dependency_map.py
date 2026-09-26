from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from app.automation_file import FileAutomation
from app.dependency_map import DependencyMapBuilder, build_inspection
from app.ha_client import SourceSnapshot
from app.references import target_key
from app.settings import Settings


def test_script_registry_identity_drives_editor_and_trace_ids() -> None:
    entity_id = "script.turn_off_light_left_on_2"
    config_id = "turn_off_light_left_on"
    snapshot = SourceSnapshot(
        states=[{"entity_id": entity_id, "state": "off", "attributes": {"id": "old-id"}}],
        home_assistant_config={"version": "2026.9.0"},
        entity_registry=[{"entity_id": entity_id, "platform": "script", "unique_id": config_id}],
        script_configs={entity_id: {"alias": "Turn off light", "sequence": []}},
        traces=[
            {
                "domain": "script",
                "item_id": config_id,
                "run_id": "registry-script-run",
                "timestamp": {"start": "2026-09-07T10:00:00+00:00"},
                "script_execution": "finished",
            }
        ],
    )

    item = build_inspection(snapshot, Settings())["scripts"][entity_id]

    assert item["config_id"] == config_id
    assert item["trace"]["run_id"] == "registry-script-run"
    assert item["status"] == "enabled"
    assert item["state"] == "off"
    assert item["configuration_source"] == "runtime"
    assert item["configuration_available"] is True
    assert item["restored"] is False
    assert item["issue_count"] == 0


@pytest.mark.parametrize(
    "registry",
    [
        {},
        {"platform": "script", "unique_id": None},
        {"platform": "script", "unique_id": ""},
        {"platform": "other", "unique_id": "different-platform-key"},
    ],
)
def test_script_without_registry_identity_keeps_its_literal_suffix(registry: dict) -> None:
    entity_id = "script.original_name_2"
    snapshot = SourceSnapshot(
        states=[{"entity_id": entity_id, "state": "off", "attributes": {}}],
        home_assistant_config={"version": "2026.9.0"},
        entity_registry=[{"entity_id": entity_id, **registry}],
        script_configs={entity_id: {"sequence": []}},
    )

    item = build_inspection(snapshot, Settings())["scripts"][entity_id]

    assert item["config_id"] == "original_name_2"


@pytest.mark.parametrize("domain", ["automation", "script"])
def test_unavailable_items_are_findings_without_dependency_errors(domain: str) -> None:
    entity_id = f"{domain}.unavailable_item"
    snapshot = SourceSnapshot(
        states=[{"entity_id": entity_id, "state": "unavailable", "attributes": {}}],
        home_assistant_config={"version": "2026.9.0"},
        automation_configs={entity_id: {"triggers": [], "actions": []}},
        script_configs={entity_id: {"sequence": []}},
    )

    report = build_inspection(snapshot, Settings())
    item = report[f"{domain}s"][entity_id]

    assert item["status"] == "unavailable"
    assert item["issue_count"] == 1
    assert item["state"] == "unavailable"
    assert item["configuration_available"] is True
    assert "does not prove that it loaded successfully" in " ".join(item["warnings"])
    assert report["summary"]["items_with_issues"] == 1


def test_restored_and_active_scripts_with_same_name_remain_distinct() -> None:
    stale_id = "script.turn_off_light_left_on"
    active_id = "script.turn_off_light_left_on_2"
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": stale_id,
                "state": "unavailable",
                "attributes": {"friendly_name": "Turn off light", "restored": True},
            },
            {
                "entity_id": active_id,
                "state": "off",
                "attributes": {"friendly_name": "Turn off light"},
            },
        ],
        home_assistant_config={"version": "2026.9.0"},
        entity_registry=[
            {"entity_id": stale_id, "platform": "script", "unique_id": "old-script"},
            {"entity_id": active_id, "platform": "script", "unique_id": "current-script"},
        ],
        script_configs={active_id: {"alias": "Turn off light", "sequence": []}},
        script_config_errors={stale_id: "not_found: Entity not found"},
    )

    report = build_inspection(snapshot, Settings())
    stale, active = (report["scripts"][entity_id] for entity_id in (stale_id, active_id))

    assert report["summary"]["scripts"] == 2
    assert report["summary"]["scripts_with_issues"] == 1
    assert stale["restored"] is True
    assert stale["configuration_available"] is False
    assert stale["configuration_source"] == "attributes"
    assert stale["config_hash"] is None
    assert any("restored placeholder" in warning for warning in stale["warnings"])
    assert "not_found: Entity not found" in stale["warnings"]
    assert active["restored"] is False
    assert active["configuration_source"] == "runtime"
    assert active["config_id"] == "current-script"
    assert active["issue_count"] == 0


def test_build_inspection_handles_targets_missing_entities_and_unloaded_yaml() -> None:
    runtime_config = {
        "id": "runtime-id",
        "alias": "Target automation",
        "triggers": [
            {
                "trigger": "battery.low",
                "target": {"area_id": "kitchen", "device_id": "missing-device"},
            }
        ],
        "conditions": [{"condition": "state", "entity_id": "binary_sensor.missing", "state": "on"}],
        "actions": [{"action": "light.turn_on", "target": {"area_id": "kitchen"}}],
    }
    unloaded_config = {
        "id": "unloaded-id",
        "alias": "Broken file automation",
        "triggers": [{"trigger": "state", "entity_id": "sensor.absent"}],
        "actions": [],
    }
    trigger_target = target_key({"area_id": ["kitchen"], "device_id": ["missing-device"]})
    action_target = target_key({"area_id": ["kitchen"]})
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.target_automation",
                "state": "on",
                "attributes": {"id": "runtime-id", "friendly_name": "Target automation"},
            },
            {
                "entity_id": "light.kitchen_main",
                "state": "on",
                "attributes": {"friendly_name": "Kitchen main"},
            },
            {
                "entity_id": "sensor.kitchen_battery",
                "state": "15",
                "attributes": {"device_class": "battery"},
            },
            {
                "entity_id": "input_boolean.orphan",
                "state": "off",
                "attributes": {"friendly_name": "Unused helper"},
            },
        ],
        home_assistant_config={"version": "2026.7.2", "location_name": "Test Home"},
        automation_configs={"automation.target_automation": runtime_config},
        file_automations=[
            FileAutomation(0, "runtime-id", runtime_config),
            FileAutomation(1, "unloaded-id", unloaded_config),
        ],
        entity_registry=[
            {"entity_id": "light.kitchen_main", "device_id": "light-device"},
            {"entity_id": "sensor.kitchen_battery", "device_id": "battery-device"},
        ],
        entity_sources={
            "light.kitchen_main": {"domain": "hue"},
            "sensor.kitchen_battery": {"domain": "mobile_app"},
        },
        trigger_descriptions={
            "battery.low": {
                "target": {
                    "entity": [{"device_class": ["battery"]}],
                    "primary_entities_only": True,
                }
            }
        },
        service_descriptions={
            "light": {"turn_on": {"target": {"entity": [{"domain": ["light"]}]}}}
        },
        target_resolutions={
            trigger_target: {
                "referenced_entities": ["sensor.kitchen_battery", "light.kitchen_main"],
                "primary_entities": ["sensor.kitchen_battery", "light.kitchen_main"],
                "missing_devices": ["missing-device"],
                "missing_areas": [],
                "missing_floors": [],
                "missing_labels": [],
            },
            action_target: {
                "referenced_entities": ["sensor.kitchen_battery", "light.kitchen_main"],
                "primary_entities": ["sensor.kitchen_battery", "light.kitchen_main"],
                "missing_devices": [],
                "missing_areas": [],
                "missing_floors": [],
                "missing_labels": [],
            },
        },
        validations={
            "runtime:automation.target_automation": {
                "triggers": {"valid": False, "error": "Unknown trigger battery.low"},
                "conditions": {"valid": True},
                "actions": {"valid": True},
            }
        },
    )

    report = build_inspection(snapshot, Settings())

    runtime = report["automations"]["automation.target_automation"]
    assert {entity["id"] for entity in runtime["entities"]} == {
        "binary_sensor.missing",
        "light.kitchen_main",
        "sensor.kitchen_battery",
    }
    assert (
        next(entity for entity in runtime["entities"] if entity["id"] == "binary_sensor.missing")[
            "status"
        ]
        == "missing"
    )
    assert report["summary"]["unloaded"] == 1
    assert report["summary"]["unresolved_targets"] == 1
    assert report["summary"]["compatibility_issues"] >= 2
    assert report["orphans"] == ["input_boolean.orphan"]
    assert "unloaded:unloaded-id" in report["automations"]
    assert len(runtime["targets"]) == 2


def test_build_inspection_classifies_disabled_registry_reference() -> None:
    config = {
        "triggers": [{"trigger": "state", "entity_id": "sensor.disabled"}],
        "actions": [],
    }
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.demo",
                "state": "off",
                "attributes": {"id": "one"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        automation_configs={"automation.demo": config},
        entity_registry=[{"entity_id": "sensor.disabled", "disabled_by": "user"}],
    )

    report = build_inspection(snapshot, Settings())

    entity = report["automations"]["automation.demo"]["entities"][0]
    assert entity["state"] == "disabled"
    assert entity["status"] == "disabled"
    assert report["summary"]["disabled_entities"] == 1


class FileAwareClient:
    def __init__(self) -> None:
        self.received: list[FileAutomation] = []

    async def fetch_snapshot(self, file_automations: list[FileAutomation]) -> SourceSnapshot:
        self.received = file_automations
        return SourceSnapshot(
            states=[],
            home_assistant_config={"version": "2026.7.2"},
            file_automations=file_automations,
        )


@pytest.mark.parametrize(
    ("config", "expected_status", "expected_kind"),
    [
        ({"variables": {"notifiers": ["notify.household"]}}, "ok", "service"),
        ({"variables": {"notifier": "{{ 'notify.household' }}"}}, "ok", "service"),
        ({"entity_id": "notify.household"}, "missing", "entity"),
        ({"target": {"entity_id": "notify.household"}}, "missing", "entity"),
        ({"value_template": "{{ states('notify.household') }}"}, "missing", "entity"),
    ],
)
def test_registered_services_do_not_mask_explicit_entity_dependencies(
    config: dict, expected_status: str, expected_kind: str
) -> None:
    snapshot = SourceSnapshot(
        states=[{"entity_id": "automation.notify", "state": "on", "attributes": {}}],
        home_assistant_config={"version": "2026.8.3"},
        automation_configs={"automation.notify": config},
        service_descriptions={"notify": {"household": {"name": "Household"}}},
    )

    report = build_inspection(snapshot, Settings())

    item = report["automations"]["automation.notify"]
    assert item["entities"][0]["status"] == expected_status
    assert item["entities"][0]["kind"] == expected_kind
    assert item["issue_count"] == (0 if expected_status == "ok" else 1)


def test_notify_repeat_values_use_service_registry_and_keep_missing_references() -> None:
    snapshot = SourceSnapshot(
        states=[{"entity_id": "automation.notify", "state": "on", "attributes": {}}],
        home_assistant_config={"version": "2026.8.3"},
        automation_configs={
            "automation.notify": {
                "actions": [
                    {
                        "repeat": {
                            "for_each": [
                                "notify.household",
                                "notify.mobile_app_phone_1",
                                "notify.missing",
                            ],
                            "sequence": [{"action": "{{ repeat.item }}"}],
                        }
                    }
                ]
            }
        },
        service_descriptions={"notify": {"household": {}, "mobile_app_phone_1": {}}},
    )

    report = build_inspection(snapshot, Settings())

    entities = report["automations"]["automation.notify"]["entities"]
    assert {entity["id"]: entity["status"] for entity in entities} == {
        "notify.household": "ok",
        "notify.mobile_app_phone_1": "ok",
        "notify.missing": "missing",
    }


@pytest.mark.parametrize("domain", ["automation", "script"])
def test_config_hash_changes_only_with_config_and_requires_available_config(domain: str) -> None:
    entity_id = f"{domain}.demo"
    config = {"alias": "Demo", "mode": "single"}
    snapshot = SourceSnapshot(
        states=[{"entity_id": entity_id, "state": "on", "attributes": {"id": "demo"}}],
        home_assistant_config={"version": "2026.8.3"},
    )
    configs = getattr(snapshot, f"{domain}_configs")
    configs[entity_id] = config

    original = build_inspection(snapshot, Settings())[f"{domain}s"][entity_id]["config_hash"]
    snapshot.states[0]["state"] = "off"
    snapshot.states[0]["attributes"]["last_triggered"] = "2026-09-05T12:00:00Z"
    configs[entity_id] = {"mode": "single", "alias": "Demo"}
    unchanged = build_inspection(snapshot, Settings())[f"{domain}s"][entity_id]["config_hash"]
    configs[entity_id]["mode"] = "parallel"
    changed = build_inspection(snapshot, Settings())[f"{domain}s"][entity_id]["config_hash"]
    configs.clear()
    unavailable = build_inspection(snapshot, Settings())[f"{domain}s"][entity_id]["config_hash"]

    assert isinstance(original, str) and len(original) == 64
    assert unchanged == original
    assert changed != original
    assert unavailable is None


@pytest.mark.anyio
async def test_builder_scans_file_and_builds_report(tmp_path: Path) -> None:
    path = tmp_path / "automations.yaml"
    path.write_text(
        "- id: file-only\n  alias: File only\n  triggers: []\n  actions: []\n",
        encoding="utf-8",
    )
    client = FileAwareClient()
    settings = Settings(automations_file=path, scan_automations_file=True)
    builder = DependencyMapBuilder(settings, client)  # type: ignore[arg-type]

    report = await builder.build()

    assert client.received[0].config_id == "file-only"
    assert report["summary"]["unloaded"] == 1
    assert report["automations"]["unloaded:file-only"]["friendly_name"] == "File only"


def test_duplicate_file_id_and_registry_only_helper_remain_visible() -> None:
    runtime_config = {
        "id": "duplicate",
        "alias": "Loaded copy",
        "triggers": [],
        "actions": [],
    }
    duplicate_config = {
        "id": "duplicate",
        "alias": "Duplicate copy",
        "triggers": [],
        "actions": [],
    }
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.loaded_copy",
                "state": "on",
                "attributes": {"id": "duplicate"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        automation_configs={"automation.loaded_copy": runtime_config},
        file_automations=[
            FileAutomation(0, "duplicate", runtime_config),
            FileAutomation(1, "duplicate", duplicate_config),
        ],
        entity_registry=[
            {
                "entity_id": "input_boolean.disabled_helper",
                "disabled_by": "user",
                "name": "Disabled helper",
            }
        ],
    )

    report = build_inspection(snapshot, Settings())

    assert report["summary"]["automations"] == 2
    assert report["automations"]["unloaded:duplicate"]["friendly_name"] == "Duplicate copy"
    assert report["unreferenced_helpers"] == [
        {
            "id": "input_boolean.disabled_helper",
            "name": "Disabled helper",
            "state": "disabled",
            "status": "disabled",
        }
    ]


def test_identical_file_duplicates_matching_loaded_automation_do_not_create_unloaded_rows() -> None:
    config = {
        "id": "duplicate",
        "alias": "Loaded copy",
        "triggers": [],
        "actions": [],
    }
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.loaded_copy",
                "state": "on",
                "attributes": {"id": "duplicate"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        automation_configs={"automation.loaded_copy": config},
        file_automations=[
            FileAutomation(0, "duplicate", config),
            FileAutomation(1, "duplicate", dict(config)),
            FileAutomation(2, "duplicate", dict(config)),
        ],
    )

    report = build_inspection(snapshot, Settings())

    assert report["summary"]["automations"] == 1
    assert report["summary"]["unloaded"] == 0
    assert list(report["automations"]) == ["automation.loaded_copy"]


def test_duplicate_file_entries_collapse_even_when_runtime_config_differs() -> None:
    file_config = {
        "id": "duplicate",
        "alias": "Loaded copy",
        "triggers": [],
        "actions": [],
    }
    runtime_config = dict(file_config) | {"mode": "single"}
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.loaded_copy",
                "state": "on",
                "attributes": {"id": "duplicate"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        automation_configs={"automation.loaded_copy": runtime_config},
        file_automations=[
            FileAutomation(0, "duplicate", dict(file_config)),
            FileAutomation(1, "duplicate", dict(file_config)),
            FileAutomation(2, "duplicate", dict(file_config)),
        ],
    )

    report = build_inspection(snapshot, Settings())

    assert report["summary"]["automations"] == 1
    assert report["summary"]["unloaded"] == 0
    assert list(report["automations"]) == ["automation.loaded_copy"]


def test_build_inspection_includes_loaded_scripts() -> None:
    script_config = {
        "alias": "Night lights",
        "sequence": [
            {"service": "light.turn_on", "target": {"entity_id": "light.hall"}},
            {"action": "notify.send_message", "data": {"message": "Done"}},
        ],
    }
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "script.night_lights",
                "state": "off",
                "attributes": {"friendly_name": "Night lights"},
            },
            {
                "entity_id": "light.hall",
                "state": "off",
                "attributes": {"friendly_name": "Hall"},
            },
        ],
        home_assistant_config={"version": "2026.7.2"},
        script_configs={"script.night_lights": script_config},
        traces=[
            {
                "domain": "script",
                "item_id": "night_lights",
                "run_id": "run-1",
                "timestamp": {"start": "2026-07-10T10:00:00+00:00"},
                "script_execution": "error",
            }
        ],
        trace_details={"script:night_lights": {"trace": {"action/0": []}}},
    )

    report = build_inspection(snapshot, Settings())
    script = report["scripts"]["script.night_lights"]

    assert report["summary"]["automations"] == 0
    assert report["summary"]["scripts"] == 1
    assert report["summary"]["inspected_items"] == 1
    assert script["item_type"] == "script"
    assert script["status"] == "enabled"
    assert {entity["id"] for entity in script["entities"]} == {"light.hall"}
    assert {finding["code"] for finding in script["compatibility_issues"]} == {
        "legacy_service_action_key"
    }
    assert script["trace"]["script_execution"] == "error"


def test_excluding_disabled_automations_keeps_idle_scripts() -> None:
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "script.idle_script",
                "state": "off",
                "attributes": {"friendly_name": "Idle script"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        script_configs={"script.idle_script": {"alias": "Idle script", "sequence": []}},
    )

    report = build_inspection(snapshot, Settings(include_disabled=False))

    assert list(report["scripts"]) == ["script.idle_script"]
    assert report["scripts"]["script.idle_script"]["status"] == "enabled"


def test_excluding_disabled_automation_does_not_report_its_file_as_unloaded() -> None:
    config = {"id": "off-id", "alias": "Off", "triggers": [], "actions": []}
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.off",
                "state": "off",
                "attributes": {"id": "off-id"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        automation_configs={"automation.off": config},
        file_automations=[FileAutomation(0, "off-id", config)],
    )

    report = build_inspection(snapshot, Settings(include_disabled=False))

    assert report["automations"] == {}
    assert report["summary"]["unloaded"] == 0


def test_runtime_template_target_is_informational_not_a_missing_dependency() -> None:
    config = {
        "id": "dynamic-id",
        "alias": "Dynamic speaker",
        "triggers": [],
        "actions": [
            {
                "action": "media_player.play_media",
                "target": {"entity_id": "{{ sonos_speaker }}"},
            }
        ],
    }
    snapshot = SourceSnapshot(
        states=[
            {
                "entity_id": "automation.dynamic_speaker",
                "state": "on",
                "attributes": {"id": "dynamic-id"},
            }
        ],
        home_assistant_config={"version": "2026.7.2"},
        automation_configs={"automation.dynamic_speaker": config},
    )

    report = build_inspection(snapshot, Settings())
    automation = report["automations"]["automation.dynamic_speaker"]

    assert automation["entities"] == []
    assert automation["issue_count"] == 0
    assert automation["targets"][0]["runtime_resolved"] is True
    assert automation["targets"][0]["dynamic_target"] == {"entity_id": ["{{ sonos_speaker }}"]}
    assert report["summary"]["missing_entities"] == 0


REGISTRY_ID = "0123456789abcdef0123456789abcdef"


def _single_target_snapshot(target: dict, domain: str = "automation") -> SourceSnapshot:
    entity_id = f"{domain}.special_target"
    action = {"action": "light.turn_off", "target": target}
    return SourceSnapshot(
        states=[
            {"entity_id": entity_id, "state": "on", "attributes": {"id": "special"}},
            {"entity_id": "light.kitchen", "state": "on", "attributes": {}},
            {"entity_id": "light.hall", "state": "off", "attributes": {}},
        ],
        home_assistant_config={"version": "2026.9.1"},
        entity_registry=[
            {"entity_id": "light.kitchen", "id": REGISTRY_ID},
            {"entity_id": "light.hall", "id": "fedcba9876543210fedcba9876543210"},
        ],
        automation_configs={entity_id: {"actions": [action]}},
        script_configs={entity_id: {"sequence": [action]}},
    )


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    ("target", "expected_entities", "entity_match"),
    [
        ({"entity_id": "all"}, [], "all"),
        ({"entity_id": "ALL"}, [], "all"),
        ({"entity_id": "none"}, [], "none"),
        ({"entity_id": ""}, [], None),
        ({"entity_id": REGISTRY_ID}, [("light.kitchen", "ok")], None),
        (
            {"entity_id": "light.kitchen, light.hall"},
            [("light.hall", "ok"), ("light.kitchen", "ok")],
            None,
        ),
        ({"entity_id": "Light.Kitchen"}, [("light.kitchen", "ok")], None),
        ({"entity_id": "Light.kitchen"}, [("light.kitchen", "ok")], None),
    ],
)
def test_home_assistant_target_selectors_do_not_break_inspection(
    domain: str, target: dict, expected_entities: list[tuple[str, str]], entity_match: str | None
) -> None:
    """Regression for #39: special target values failed the entire inspection."""
    report = build_inspection(_single_target_snapshot(target, domain), Settings())

    item = report[f"{domain}s"][f"{domain}.special_target"]
    assert [(entity["id"], entity["status"]) for entity in item["entities"]] == expected_entities
    assert item["issue_count"] == 0
    assert item["compatibility_issues"] == [] or all(
        finding["severity"] == "info" for finding in item["compatibility_issues"]
    )
    if entity_match or expected_entities:
        assert item["targets"][0]["entity_match"] == entity_match
    assert report["summary"]["missing_entities"] == 0


def test_unknown_entity_registry_target_is_a_missing_dependency() -> None:
    unknown = "ffffffffffffffffffffffffffffffff"

    report = build_inspection(_single_target_snapshot({"entity_id": unknown}), Settings())

    item = report["automations"]["automation.special_target"]
    assert item["entities"] == [
        {
            "id": unknown,
            "domain": None,
            "kind": "entity",
            "name": "Unknown entity registry ID",
            "state": "missing",
            "status": "missing",
            "ok": False,
            "sources": ["action_target"],
            "device_id": None,
            "area_id": None,
        }
    ]
    assert item["targets"][0]["entity_ids"] == [unknown]
    assert item["issue_count"] == 1
    assert report["summary"]["missing_entities"] == 1


def test_analysis_failure_is_isolated_to_the_affected_item(monkeypatch, caplog) -> None:
    import app.dependency_map as dependency_map

    original = dependency_map.collect_entity_references

    def fail_for_broken(config: dict, known_domains: set[str]) -> dict[str, set[str]]:
        if config.get("alias") == "Broken":
            raise ValueError("not enough values to unpack (expected 2, got 1)")
        return original(config, known_domains)

    monkeypatch.setattr(dependency_map, "collect_entity_references", fail_for_broken)
    healthy = {"alias": "Healthy", "triggers": [{"trigger": "state", "entity_id": "light.hall"}]}
    snapshot = SourceSnapshot(
        states=[
            {"entity_id": "automation.broken", "state": "on", "attributes": {"id": "broken"}},
            {"entity_id": "automation.healthy", "state": "on", "attributes": {"id": "healthy"}},
            {"entity_id": "light.hall", "state": "on", "attributes": {}},
        ],
        home_assistant_config={"version": "2026.9.1"},
        automation_configs={
            "automation.broken": {"alias": "Broken", "actions": []},
            "automation.healthy": healthy,
        },
        warnings=["Existing source warning"],
    )

    report = build_inspection(snapshot, Settings())

    broken = report["automations"]["automation.broken"]
    assert broken["status"] == "enabled"
    assert broken["entities"] == []
    assert broken["issue_count"] == 1
    assert [finding["code"] for finding in broken["compatibility_issues"]] == ["analysis_failed"]
    assert "ValueError: not enough values to unpack" in broken["compatibility_issues"][0]["message"]
    assert broken["config_hash"] is not None
    healthy_item = report["automations"]["automation.healthy"]
    assert [entity["id"] for entity in healthy_item["entities"]] == ["light.hall"]
    assert healthy_item["issue_count"] == 0
    assert report["summary"]["items_with_issues"] == 1
    assert report["warnings"][0] == "Existing source warning"
    assert "automation.broken" in report["warnings"][1]
    assert snapshot.warnings == ["Existing source warning"]
    assert "automation.broken" in caplog.text
    assert "Traceback" in caplog.text


def test_yaml_scalar_display_fields_are_json_safe() -> None:
    config = {
        "id": "holiday",
        "alias": datetime.date(2026, 12, 25),
        "mode": datetime.time(7, 30),
        "triggers": [],
        "actions": [],
    }
    snapshot = SourceSnapshot(
        states=[],
        home_assistant_config={"version": "2026.9.1"},
        file_automations=[FileAutomation(0, "holiday", config)],
    )

    report = build_inspection(snapshot, Settings())

    item = report["automations"]["unloaded:holiday"]
    assert item["friendly_name"] == "2026-12-25"
    assert item["mode"] == "07:30:00"
    json.dumps(report, sort_keys=True)


def test_unfingerprintable_configuration_is_isolated() -> None:
    config = {"id": "mixed", "variables": {1: "one", "two": 2}, "actions": []}
    snapshot = SourceSnapshot(
        states=[],
        home_assistant_config={"version": "2026.9.1"},
        file_automations=[FileAutomation(0, "mixed", config)],
    )

    report = build_inspection(snapshot, Settings())

    item = report["automations"]["unloaded:mixed"]
    assert item["config_hash"] is None
    assert [finding["code"] for finding in item["compatibility_issues"]] == ["analysis_failed"]
