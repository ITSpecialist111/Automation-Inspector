from __future__ import annotations

import re
from pathlib import Path

import yaml

from app import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "automation_inspector"


def test_home_assistant_app_manifest_is_ingress_only_and_current() -> None:
    manifest = yaml.safe_load((APP / "config.yaml").read_text(encoding="utf-8"))

    assert manifest["version"] == APP_VERSION
    assert manifest["homeassistant"] == "2026.7.0"
    assert manifest["arch"] == ["aarch64", "amd64"]
    assert manifest["image"] == "ghcr.io/itspecialist111/automation-inspector"
    assert manifest["ingress"] is True
    assert manifest["panel_admin"] is True
    assert manifest["homeassistant_api"] is True
    assert "ports" not in manifest
    assert manifest["map"] == [
        {
            "type": "homeassistant_config",
            "read_only": True,
            "path": "/homeassistant",
        }
    ]
    assert set(manifest["options"]) == set(manifest["schema"])


def test_dashboard_uses_safe_dom_and_nonce_bootstrap() -> None:
    html = (APP / "www" / "index.html").read_text(encoding="utf-8")
    javascript = (APP / "www" / "app.js").read_text(encoding="utf-8")
    css = (APP / "www" / "styles.css").read_text(encoding="utf-8")

    assert 'nonce="__CSP_NONCE__"' in html
    assert 'src="static/app.js"' in html
    assert "innerHTML" not in javascript
    assert "insertAdjacentHTML" not in javascript
    assert "eval(" not in javascript
    assert "--cp-bg: #f7f4ef;" in css
    assert "--cp-accent: #b11f4b;" in css


def test_container_is_non_root_and_health_checked() -> None:
    dockerfile = (APP / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (APP / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert re.fullmatch(r"FROM python:3\.14\.\d+-alpine3\.24", dockerfile.splitlines()[0])
    assert "adduser -S -D -H -G inspector inspector" in dockerfile
    assert 'ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]' in dockerfile
    assert "AI_OPTIONS_PATH=/tmp/options.json" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert 'io.hass.type="app"' in dockerfile

    # Supervisor writes /data/options.json as root with mode 0600, so the
    # entrypoint must stage a readable copy before dropping privileges.
    assert "/data/options.json" in entrypoint
    assert "exec su-exec inspector:inspector" in entrypoint
    # read_text normalizes newlines, so assert on raw bytes: CRLF would make
    # the script unrunnable inside the Alpine container.
    assert b"\r\n" not in (APP / "docker-entrypoint.sh").read_bytes()
