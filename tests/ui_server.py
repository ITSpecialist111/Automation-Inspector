"""Synthetic inspection server for browser tests and local UI previews."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.automation_file import FileAutomation
from app.dependency_map import build_inspection
from app.ha_client import SourceSnapshot
from app.main import create_app
from app.service import InspectionService
from app.settings import Settings


class FixtureBuilder:
    async def build(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        definitions: list[tuple[str, str, str, dict[str, Any]]] = [
            (
                "laundry_reminder",
                "Laundry reminder",
                "on",
                {
                    "actions": [
                        {
                            "action": "notify.household",
                            "data": {"message": "{{ has_value('sensor.washing_machine') }}"},
                        }
                    ]
                },
            ),
            (
                "evening_lights",
                "Evening lights",
                "on",
                {
                    "actions": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": ["light.living_room", "light.hallway"]},
                        }
                    ]
                },
            ),
            (
                "front_door_alert",
                "Front door alert",
                "on",
                {
                    "triggers": [
                        {
                            "trigger": "door.opened",
                            "target": {"entity_id": "binary_sensor.front_door"},
                            "options": {"behavior": "any"},
                        }
                    ]
                },
            ),
            (
                "garden_irrigation",
                "Garden irrigation",
                "on",
                {
                    "conditions": [
                        {
                            "condition": "state",
                            "entity_id": "sensor.garden_moisture",
                            "state": "dry",
                        }
                    ]
                },
            ),
            (
                "heating_schedule",
                "Heating schedule",
                "off",
                {
                    "actions": [
                        {
                            "action": "climate.set_temperature",
                            "target": {"entity_id": "climate.office"},
                            "data": {"temperature": 20},
                        }
                    ]
                },
            ),
            (
                "arrival_notification",
                "Arrival notification",
                "on",
                {
                    "actions": [
                        {
                            "repeat": {
                                "for_each": ["notify.household", "notify.mobile_app_phone"],
                                "sequence": [{"action": "{{ repeat.item }}"}],
                            }
                        }
                    ]
                },
            ),
            (
                "morning_briefing",
                "Morning briefing",
                "on",
                {
                    "actions": [
                        {
                            "action": "media_player.play_media",
                            "target": {"entity_id": "media_player.kitchen"},
                        }
                    ]
                },
            ),
            (
                "bedtime",
                "Bedtime routine",
                "on",
                {
                    "actions": [
                        {"action": "light.turn_off", "target": {"entity_id": "light.living_room"}}
                    ]
                },
            ),
        ]
        snapshot = SourceSnapshot(
            states=[],
            home_assistant_config={"version": "2026.8.3", "location_name": "Demo Home"},
            service_descriptions={"notify": {"household": {}, "mobile_app_phone": {}}},
            file_automations=[
                FileAutomation(
                    0,
                    "retired",
                    {
                        "id": "retired",
                        "alias": "Retired porch light",
                        "actions": [],
                    },
                )
            ],
        )
        for index, (object_id, name, status, config) in enumerate(definitions):
            entity_id = f"automation.{object_id}"
            snapshot.states.append(
                {
                    "entity_id": entity_id,
                    "state": status,
                    "attributes": {
                        "id": object_id,
                        "friendly_name": name,
                        "last_triggered": None
                        if index == 3
                        else (now - timedelta(hours=index + 1)).isoformat(),
                    },
                }
            )
            snapshot.automation_configs[entity_id] = {
                "id": object_id,
                "alias": name,
                "mode": "single",
                **config,
            }
        for object_id, name in [
            ("good_night", "Good night"),
            ("movie_time", "Movie time"),
            ("announce", "Announce to household"),
        ]:
            entity_id = f"script.{object_id}"
            snapshot.states.append(
                {
                    "entity_id": entity_id,
                    "state": "off",
                    "attributes": {
                        "friendly_name": name,
                        "last_triggered": (now - timedelta(days=40)).isoformat(),
                    },
                }
            )
            snapshot.script_configs[entity_id] = {
                "alias": name,
                "mode": "single",
                "sequence": [
                    {"action": "notify.household", "data": {"message": "Example message"}}
                ],
            }
        for entity_id, name, value in [
            ("sensor.washing_machine", "Washing machine", "unavailable"),
            ("light.living_room", "Living room", "on"),
            ("light.hallway", "Hallway", "off"),
            ("binary_sensor.front_door", "Front door", "off"),
            ("climate.office", "Office thermostat", "unavailable"),
            ("media_player.kitchen", "Kitchen speaker", "idle"),
            ("input_boolean.holiday_mode", "Holiday mode", "off"),
            ("timer.tea", "Tea timer", "idle"),
        ]:
            snapshot.states.append(
                {"entity_id": entity_id, "state": value, "attributes": {"friendly_name": name}}
            )
        snapshot.traces = [
            {
                "domain": "automation",
                "item_id": "morning_briefing",
                "run_id": "sample-run",
                "timestamp": {"start": now.isoformat()},
                "state": "stopped",
                "script_execution": "error",
                "error": "Media source is no longer available",
            }
        ]
        return build_inspection(snapshot, Settings())


settings = Settings(refresh_interval=86400, scan_automations_file=False)
app = create_app(settings, InspectionService(FixtureBuilder(), settings))
