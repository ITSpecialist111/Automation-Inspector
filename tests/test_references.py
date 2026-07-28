from app.references import collect_entity_references, iter_target_uses


def test_extracts_arbitrary_entity_domains_and_templates_but_not_services() -> None:
    config = {
        "triggers": [{"trigger": "state", "entity_id": "custom_domain.alpha"}],
        "conditions": [
            {
                "condition": "template",
                "value_template": "{{ is_state('sensor.weather', 'ok') }}",
            }
        ],
        "actions": [
            {
                "action": "light.turn_on",
                "target": {"entity_id": ["light.office", "light.missing"]},
            }
        ],
    }

    references = collect_entity_references(config, {"custom_domain"})

    assert "custom_domain.alpha" in references
    assert references["sensor.weather"] == {"template"}
    assert "light.office" in references
    assert "light.turn_on" not in references
    assert "state" not in references


def test_collects_modern_multidimensional_targets() -> None:
    config = {
        "triggers": [
            {
                "trigger": "battery.became_low",
                "target": {
                    "device_id": ["device-a"],
                    "area_id": "kitchen",
                    "floor_id": "ground",
                    "label_id": ["important"],
                },
            }
        ]
    }

    uses = iter_target_uses(config)

    assert len(uses) == 1
    assert uses[0].kind == "trigger"
    assert uses[0].component == "battery.became_low"
    assert uses[0].target["floor_id"] == ["ground"]


def test_partitions_runtime_templates_from_static_targets() -> None:
    config = {
        "actions": [
            {
                "action": "media_player.play_media",
                "target": {
                    "entity_id": [
                        "media_player.office",
                        "{{ sonos_speaker }}",
                        "media_player.{{ room }}",
                    ]
                },
            }
        ]
    }

    uses = iter_target_uses(config)
    references = collect_entity_references(config, {"media_player"})

    assert uses[0].target == {"entity_id": ["media_player.office"]}
    assert uses[0].dynamic_target == {
        "entity_id": ["media_player.{{ room }}", "{{ sonos_speaker }}"]
    }
    assert references == {"media_player.office": {"action_target", "explicit"}}


def test_ignores_event_type_but_keeps_event_entity_data() -> None:
    config = {
        "triggers": [
            {
                "trigger": "event",
                "event_type": "timer.finished",
                "event_data": {"entity_id": "timer.test"},
            }
        ],
        "actions": [],
    }

    references = collect_entity_references(config, set())

    assert references == {"timer.test": {"explicit"}}
