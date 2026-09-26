import pytest

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


def test_script_field_metadata_is_not_a_dependency() -> None:
    config = {
        "fields": {
            "counter_helper": {
                "name": "Counter (**counter.fan_run_time_***)",
                "example": "counter.fan_run_time_first_floor",
                "default": "counter.real_default",
                "selector": {"entity": {"filter": [{"integration": "counter"}]}},
            },
            "text_helper": {
                "name": "Text_Input (**input_text.fan_run_time_***)",
                "example": "input_text.fan_run_time_first_floor",
            },
        },
        "sequence": [
            {
                "action": "script.process_fields",
                "data": {"fields": {"entity_id": "sensor.runtime_field"}},
            }
        ],
    }

    references = collect_entity_references(config, set())

    assert references == {
        "counter.real_default": {"configuration"},
        "sensor.runtime_field": {"explicit"},
    }


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        (
            "{% set light = namespace(data={}) %}"
            "{% set light.data = dict(light.data, transition=2) %}"
            "{{ light.data }} {{ states('light.real') }} {{ states.light.other.state }}",
            {"light.real", "light.other"},
        ),
        (
            "{% for sensor in sensors %}{{ sensor.state }}{% endfor %}"
            "{{ has_value('sensor.real') }} {{ states['sensor.other'] }}",
            {"sensor.real", "sensor.other"},
        ),
        (
            "{# sensor.not_a_dependency #}{{ 'notify.household' }}",
            {"notify.household"},
        ),
    ],
)
def test_template_parser_distinguishes_local_variables_from_entities(
    template: str, expected: set[str]
) -> None:
    references = collect_entity_references({"variables": {"result": template}}, set())

    assert set(references) == expected


REGISTRY_ID = "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize(
    ("entity_value", "entity_ids", "registry_ids", "match"),
    [
        ("all", [], (), "all"),
        ("ALL", [], (), "all"),
        ("none", [], (), "none"),
        ("light.kitchen, Light.Hall", ["light.hall", "light.kitchen"], (), None),
        (["Light.Kitchen", REGISTRY_ID], ["light.kitchen"], (REGISTRY_ID,), None),
        ("Light.kitchen", ["light.kitchen"], (), None),
        ("light.living_Room", ["light.living_room"], (), None),
        ("Binary_Sensor.front_door", ["binary_sensor.front_door"], (), None),
    ],
)
def test_action_target_entities_follow_home_assistant_selector_rules(
    entity_value: object,
    entity_ids: list[str],
    registry_ids: tuple[str, ...],
    match: str | None,
) -> None:
    config = {"actions": [{"action": "light.turn_off", "target": {"entity_id": entity_value}}]}

    uses = iter_target_uses(config)
    references = collect_entity_references(config, {"light"})

    assert len(uses) == 1
    assert uses[0].target == ({"entity_id": entity_ids} if entity_ids else {})
    assert uses[0].entity_registry_ids == registry_ids
    assert uses[0].entity_match == match
    assert sorted(references) == entity_ids
    assert all("." in entity_id for entity_id in references)


@pytest.mark.parametrize(
    "target",
    [
        {"entity_id": ""},
        {"entity_id": ["", "not an entity", "light.double__underscore", "light._leading"]},
        {"device_id": "none", "area_id": "none", "floor_id": "none", "label_id": "none"},
        # Home Assistant only accepts lowercase registry IDs (cv.fake_uuid4_hex).
        {"entity_id": REGISTRY_ID.upper()},
    ],
)
def test_invalid_or_empty_target_selectors_are_not_sent_for_resolution(target: dict) -> None:
    config = {"actions": [{"action": "light.turn_on", "target": target}]}

    assert iter_target_uses(config) == []
    assert all("." in entity_id for entity_id in collect_entity_references(config, {"light"}))


def test_special_entity_selector_keeps_other_static_and_runtime_selectors() -> None:
    config = {
        "actions": [
            {
                "action": "light.turn_off",
                "target": {"entity_id": "all", "area_id": "kitchen", "label_id": "{{ label }}"},
            },
            {"action": "light.turn_on", "target": {"entity_id": "{{ lights }}, light.hall"}},
        ]
    }

    first, second = iter_target_uses(config)

    assert first.target == {"area_id": ["kitchen"]}
    assert first.dynamic_target == {"label_id": ["{{ label }}"]}
    assert first.entity_match == "all"
    assert second.target == {}
    assert second.dynamic_target == {"entity_id": ["{{ lights }}, light.hall"]}


def test_explicit_entity_fields_match_case_insensitively_without_fragments() -> None:
    config = {
        "triggers": [
            {"trigger": "state", "entity_id": ["Binary_Sensor.Front_Door", "Light.kitchen"]}
        ],
        "conditions": [{"condition": "state", "entity_id": "light.living_Room", "state": "on"}],
        "variables": {"chosen": "light.living_Room", "label": "Light.On at dusk"},
        "actions": [],
    }

    references = collect_entity_references(config, {"light", "binary_sensor"})

    assert references == {
        "binary_sensor.front_door": {"explicit"},
        "light.kitchen": {"explicit"},
        "light.living_room": {"explicit"},
    }
