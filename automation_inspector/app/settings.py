"""Runtime settings loaded from Home Assistant app options and environment variables."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

LOG = logging.getLogger(__name__)


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, int):
        return bool(value)
    return default


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _websocket_url_from_endpoint(endpoint: str) -> str:
    """Derive a direct or Supervisor-proxied WebSocket URL for local development."""
    parsed = urlsplit(endpoint.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = parsed.path.rstrip("/")
    if path.endswith("/core"):
        path = f"{path}/websocket"
    elif not path.endswith("/websocket"):
        path = f"{path}/api/websocket"
    return urlunsplit((scheme, parsed.netloc, path, "", ""))


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application settings."""

    websocket_url: str = "ws://supervisor/core/websocket"
    token: str = ""
    refresh_interval: int = 300
    request_timeout: int = 15
    include_disabled: bool = True
    inspect_traces: bool = True
    scan_automations_file: bool = True
    automations_file: Path = Path("/homeassistant/automations.yaml")
    websocket_max_size: int = 32 * 1024 * 1024
    options_path: Path = Path("/data/options.json")

    @classmethod
    def load(cls) -> Settings:
        """Load settings, with environment variables overriding app options."""
        options_path = Path(os.getenv("AI_OPTIONS_PATH", "/data/options.json"))
        options: dict[str, Any] = {}
        if options_path.is_file():
            try:
                raw = json.loads(options_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    options = raw
            except (OSError, json.JSONDecodeError) as exc:
                LOG.warning("Unable to read app options from %s: %s", options_path, exc)

        endpoint = os.getenv("SUPERVISOR_ENDPOINT")
        websocket_url = os.getenv("HA_WS_URL")
        if not websocket_url and endpoint:
            websocket_url = _websocket_url_from_endpoint(endpoint)

        refresh_value = os.getenv(
            "AI_REFRESH_INTERVAL",
            os.getenv("AI_CACHE_TTL", options.get("refresh_interval", 300)),
        )
        return cls(
            websocket_url=websocket_url or "ws://supervisor/core/websocket",
            token=str(os.getenv("SUPERVISOR_TOKEN") or os.getenv("HA_TOKEN") or ""),
            refresh_interval=_as_int(refresh_value, 300, 30, 86400),
            request_timeout=_as_int(
                os.getenv("AI_REQUEST_TIMEOUT", options.get("request_timeout", 15)),
                15,
                3,
                120,
            ),
            include_disabled=_as_bool(
                os.getenv("AI_INCLUDE_DISABLED", options.get("include_disabled", True)),
                True,
            ),
            inspect_traces=_as_bool(
                os.getenv("AI_INSPECT_TRACES", options.get("inspect_traces", True)),
                True,
            ),
            scan_automations_file=_as_bool(
                os.getenv(
                    "AI_SCAN_AUTOMATIONS_FILE",
                    options.get("scan_automations_file", True),
                ),
                True,
            ),
            automations_file=Path(
                os.getenv("AI_AUTOMATIONS_FILE", "/homeassistant/automations.yaml")
            ),
            websocket_max_size=_as_int(os.getenv("AI_WEBSOCKET_MAX_MIB", 32), 32, 1, 128)
            * 1024
            * 1024,
            options_path=options_path,
        )
