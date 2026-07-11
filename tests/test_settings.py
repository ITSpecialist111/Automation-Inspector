from __future__ import annotations

import json
from pathlib import Path

from app.settings import Settings


def test_settings_loads_options_and_environment_override(tmp_path: Path, monkeypatch) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps(
            {
                "refresh_interval": 600,
                "request_timeout": 22,
                "include_disabled": False,
                "inspect_traces": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_OPTIONS_PATH", str(options))
    monkeypatch.setenv("AI_REFRESH_INTERVAL", "120")
    monkeypatch.setenv("SUPERVISOR_ENDPOINT", "http://supervisor/core")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "secret")

    settings = Settings.load()

    assert settings.refresh_interval == 120
    assert settings.request_timeout == 22
    assert settings.include_disabled is False
    assert settings.inspect_traces is False
    assert settings.websocket_url == "ws://supervisor/core/websocket"
    assert settings.token == "secret"


def test_settings_clamps_unsafe_values(tmp_path: Path, monkeypatch) -> None:
    options = tmp_path / "options.json"
    options.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AI_OPTIONS_PATH", str(options))
    monkeypatch.setenv("AI_REFRESH_INTERVAL", "1")
    monkeypatch.setenv("AI_WEBSOCKET_MAX_MIB", "1000")

    settings = Settings.load()

    assert settings.refresh_interval == 30
    assert settings.websocket_max_size == 128 * 1024 * 1024
