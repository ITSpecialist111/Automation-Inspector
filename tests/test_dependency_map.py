from __future__ import annotations

from pathlib import Path

import pytest

from app.automation_file import FileAutomation
from app.dependency_map import DependencyMapBuilder, build_inspection
from app.ha_client import SourceSnapshot
from app.references import target_key
from app.settings import Settings


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
