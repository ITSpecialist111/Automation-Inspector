from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.automation_file import scan_automations_file


@pytest.mark.anyio
async def test_scan_automations_file_handles_home_assistant_tags(tmp_path: Path) -> None:
    path = tmp_path / "automations.yaml"
    path.write_text(
        """
- id: '123'
  alias: Tagged automation
  variables:
    secret: !secret api_key
  triggers:
    - trigger: state
      entity_id: input_boolean.demo
  actions: []
""",
        encoding="utf-8",
    )

    result = await scan_automations_file(path, enabled=True)

    assert result.warnings == []
    assert result.automations[0].config_id == "123"
    assert result.automations[0].config["variables"]["secret"] == "api_key"


@pytest.mark.anyio
async def test_scan_automations_file_reports_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "automations.yaml"
    path.write_text("alias: not-a-list\n", encoding="utf-8")

    result = await scan_automations_file(path, enabled=True)

    assert result.automations == []
    assert "Expected a list" in result.warnings[0]


@pytest.mark.anyio
async def test_scan_missing_or_disabled_file_is_empty(tmp_path: Path) -> None:
    missing = await scan_automations_file(tmp_path / "missing.yaml", enabled=True)
    disabled = await scan_automations_file(tmp_path / "missing.yaml", enabled=False)

    assert missing.automations == []
    assert missing.warnings == []
    assert disabled == missing


@pytest.mark.anyio
async def test_scan_reports_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "automations.yaml"
    path.write_text("- id: [unterminated\n", encoding="utf-8")

    result = await scan_automations_file(path, enabled=True)

    assert result.automations == []
    assert "Unable to parse" in result.warnings[0]


@pytest.mark.anyio
async def test_yaml_only_types_match_home_assistant_json_configs(tmp_path: Path) -> None:
    path = tmp_path / "automations.yaml"
    path.write_text(
        """
- id: 1700000000000
  alias: 2026-12-25
  variables:
    3: three
    two: 2
    on: enabled
    flags: !!set {a: null}
  actions:
    - action: input_datetime.set_datetime
      data:
        datetime: 2026-12-25 07:30:00
""",
        encoding="utf-8",
    )

    result = await scan_automations_file(path, enabled=True)

    automation = result.automations[0]
    assert automation.config_id == "1700000000000"
    assert automation.config["id"] == 1700000000000
    assert automation.config["alias"] == "2026-12-25"
    assert automation.config["variables"] == {
        "3": "three",
        "two": 2,
        "true": "enabled",
        "flags": ["a"],
    }
    assert automation.config["actions"][0]["data"]["datetime"] == "2026-12-25T07:30:00"
    json.dumps(automation.config, sort_keys=True, allow_nan=False)
