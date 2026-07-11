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
