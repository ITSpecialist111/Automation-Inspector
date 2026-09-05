from app.compatibility import inspect_compatibility


def test_detects_home_assistant_2026_7_renames() -> None:
    config = {
        "triggers": [
            {
                "trigger": "battery.low",
                "target": {"device_id": "abc"},
                "options": {"behavior": "any"},
            }
        ],
        "conditions": [
            {
                "condition": "climate.target_temperature",
                "target": {"entity_id": "climate.office"},
            }
        ],
        "actions": [{"service": "light.turn_on"}],
    }

    findings = inspect_compatibility(config)
    replacements = {finding["replacement"] for finding in findings}

    assert "battery.became_low" in replacements
    assert "climate.is_target_temperature" in replacements
    assert "each" in replacements
    assert "action" in replacements


def test_detects_modern_top_level_key_migrations_without_false_error() -> None:
    findings = inspect_compatibility(
        {"trigger": [], "condition": [], "action": [], "mode": "single"}
    )

    assert {finding["replacement"] for finding in findings} == {
        "triggers",
        "conditions",
        "actions",
    }
    assert all(finding["severity"] == "info" for finding in findings)


def test_target_behavior_migration_only_applies_to_triggers() -> None:
    config = {
        "triggers": [
            {
                "trigger": "window.opened",
                "target": {"entity_id": "binary_sensor.window"},
                "options": {"behavior": "any"},
            }
        ],
        "conditions": [
            {
                "condition": "or",
                "conditions": [
                    {
                        "condition": "window.is_open",
                        "target": {"entity_id": "binary_sensor.window"},
                        "options": {"behavior": behavior},
                    }
                    for behavior in ("any", "all")
                ],
            }
        ],
        "actions": [
            {
                "action": "script.example",
                "target": {"entity_id": "script.example"},
                "options": {"behavior": "any"},
            },
            {
                "wait_for_trigger": [
                    {
                        "trigger": "door.opened",
                        "target": {"entity_id": "binary_sensor.door"},
                        "options": {"behavior": "last"},
                    }
                ]
            },
        ],
    }

    findings = inspect_compatibility(config)

    assert [(finding["path"], finding["replacement"]) for finding in findings] == [
        ("$.triggers[0].options.behavior", "each"),
        ("$.actions[1].wait_for_trigger[0].options.behavior", "all"),
    ]
