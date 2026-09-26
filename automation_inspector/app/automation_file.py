"""Read UI-managed automations that may have failed to load in Home Assistant."""

from __future__ import annotations

import asyncio
import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MAX_AUTOMATIONS_FILE_SIZE = 10 * 1024 * 1024


class _HomeAssistantSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that preserves unknown Home Assistant tags as plain data."""


def _construct_unknown_tag(
    loader: _HomeAssistantSafeLoader, _tag_suffix: str, node: yaml.Node
) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


_HomeAssistantSafeLoader.add_multi_constructor("!", _construct_unknown_tag)


def _load_yaml(text: str) -> Any:
    loader = _HomeAssistantSafeLoader(text)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


def _json_key(key: Any) -> str:
    if isinstance(key, str):
        return key
    if isinstance(key, (datetime.date, datetime.time)):
        return key.isoformat()
    return json.dumps(key) if key is None or isinstance(key, (bool, int, float)) else str(key)


def _json_compatible(value: Any) -> Any:
    """Represent YAML-only types as Home Assistant's JSON API returns runtime configs.

    YAML dates, times, sets, and non-string keys would otherwise break sorting,
    fingerprints, and WebSocket requests for the whole inspection.
    """
    if isinstance(value, dict):
        return {_json_key(key): _json_compatible(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, (set, frozenset)):
        # Sorted so configuration fingerprints stay stable across restarts.
        return sorted((_json_compatible(item) for item in value), key=repr)
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


@dataclass(frozen=True, slots=True)
class FileAutomation:
    """An automation read directly from automations.yaml."""

    index: int
    config_id: str | None
    config: dict[str, Any]

    @property
    def key(self) -> str:
        return f"file:{self.config_id or self.index}:{self.index}"


@dataclass(frozen=True, slots=True)
class FileScanResult:
    automations: list[FileAutomation]
    warnings: list[str]


def _read_file(path: Path) -> FileScanResult:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return FileScanResult([], [f"Unable to inspect {path}: {exc}"])
    if size > MAX_AUTOMATIONS_FILE_SIZE:
        return FileScanResult(
            [],
            [
                f"Skipped {path}: file is larger than "
                f"{MAX_AUTOMATIONS_FILE_SIZE // (1024 * 1024)} MiB"
            ],
        )

    try:
        loaded = _load_yaml(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return FileScanResult([], [f"Unable to parse {path}: {exc}"])

    if loaded is None:
        return FileScanResult([], [])
    if isinstance(loaded, dict) and isinstance(loaded.get("automation"), list):
        loaded = loaded["automation"]
    if not isinstance(loaded, list):
        return FileScanResult([], [f"Expected a list of automations in {path}"])

    automations: list[FileAutomation] = []
    for index, item in enumerate(loaded):
        if not isinstance(item, dict):
            continue
        config = _json_compatible(item)
        raw_id = config.get("id")
        config_id = str(raw_id) if raw_id is not None else None
        automations.append(FileAutomation(index, config_id, config))
    return FileScanResult(automations, [])


async def scan_automations_file(path: Path, enabled: bool) -> FileScanResult:
    """Read automations.yaml without blocking the event loop."""
    if not enabled:
        return FileScanResult([], [])

    def read_if_present() -> FileScanResult:
        return _read_file(path) if path.is_file() else FileScanResult([], [])

    return await asyncio.to_thread(read_if_present)
