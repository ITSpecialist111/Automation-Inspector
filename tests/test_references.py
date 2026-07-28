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


def test_ignores_entity_like_values_in_description() -> None:
    config = {
        "description": "Removed binary_sensor.old_tracker and notify.send_message here.",
        "triggers": [{"trigger": "state", "entity_id": "sensor.real_dependency"}],
        "actions": [],
    }

    references = collect_entity_references(config, set())

    assert references == {"sensor.real_dependency": {"explicit"}}


def test_ignores_jinja_context_paths_but_keeps_literal_template_entities() -> None:
    config = {
        "conditions": [
            {
                "condition": "template",
                "value_template": "{{ is_state('sensor.real_temperature', '20') }}",
            }
        ],
        "actions": [
            {
                "repeat": {
                    "for_each": [{"boolean": "input_boolean.window_pause"}],
                    "sequence": [
                        {
                            "action": "input_boolean.turn_off",
                            "target": {"entity_id": "{{ repeat.item.boolean }}"},
                        },
                        {
                            "action": "logbook.log",
                            "data": {"message": "Triggered by {{ trigger.entity_id }}"},
                        },
                    ],
                }
            }
        ],
    }

    references = collect_entity_references(config, set())

    assert references == {
        "input_boolean.window_pause": {"configuration"},
        "sensor.real_temperature": {"template"},
    }


def test_keeps_template_entity_references_not_matched_by_helper_functions() -> None:
    config = {
        "conditions": [
            {"condition": "template", "value_template": "{{ has_value('sensor.alpha') }}"},
            {"condition": "template", "value_template": "{{ states.sensor.beta }}"},
            {
                "condition": "template",
                "value_template": (
                    "{% if is_state('binary_sensor.door','on') "
                    "and has_value('sensor.temp') %}on{% endif %}"
                ),
            },
        ],
        "actions": [],
    }

    references = collect_entity_references(config, {"sensor", "binary_sensor"})

    assert sorted(references) == [
        "binary_sensor.door",
        "sensor.alpha",
        "sensor.beta",
        "sensor.temp",
    ]
