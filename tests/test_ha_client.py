from __future__ import annotations

import json

import pytest
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed, WebSocketException

import app.ha_client as ha_client_module
from app.ha_client import HomeAssistantClient, HomeAssistantConnectionError
from app.references import target_key
from app.settings import Settings


@pytest.mark.anyio
async def test_home_assistant_client_fetches_complete_websocket_snapshot() -> None:
    automation_config = {
        "id": "one",
        "alias": "WebSocket automation",
        "triggers": [
            {
                "trigger": "battery.became_low",
                "target": {"area_id": "kitchen"},
            }
        ],
        "actions": [
            {"action": "light.turn_on", "target": {"area_id": "kitchen"}},
            {
                "action": "media_player.play_media",
                "target": {"entity_id": "{{ sonos_speaker }}"},
            },
        ],
    }
    received_types: list[str] = []
    resolved_targets: list[dict[str, object]] = []

    async def handler(websocket: ServerConnection) -> None:
        await websocket.send(json.dumps({"type": "auth_required"}))
        auth = json.loads(await websocket.recv())
        assert auth == {"type": "auth", "access_token": "test-token"}
        await websocket.send(json.dumps({"type": "auth_ok", "ha_version": "2026.7.2"}))
        try:
            async for raw in websocket:
                request = json.loads(raw)
                request_id = request["id"]
                request_type = request["type"]
                received_types.append(request_type)

                if request_type == "get_states":
                    result = [
                        {
                            "entity_id": "automation.websocket_automation",
                            "state": "on",
                            "attributes": {"id": "one"},
                        },
                        {
                            "entity_id": "sensor.kitchen_battery",
                            "state": "12",
                            "attributes": {"device_class": "battery"},
                        },
                    ]
                elif request_type == "get_config":
                    result = {"version": "2026.7.2", "location_name": "Socket Home"}
                elif request_type == "config/entity_registry/list":
                    result = [
                        {
                            "entity_id": "sensor.kitchen_battery",
                            "device_id": "battery-device",
                        }
                    ]
                elif request_type == "config/device_registry/list":
                    result = [{"id": "battery-device", "name": "Battery"}]
                elif request_type == "config/area_registry/list":
                    result = [{"area_id": "kitchen", "name": "Kitchen"}]
                elif request_type == "config/floor_registry/list":
                    result = [{"floor_id": "ground", "name": "Ground"}]
                elif request_type == "config/label_registry/list":
                    await websocket.send(
                        json.dumps(
                            {
                                "id": request_id,
                                "type": "result",
                                "success": False,
                                "error": {
                                    "code": "unknown_command",
                                    "message": "Labels unavailable",
                                },
                            }
                        )
                    )
                    continue
                elif request_type == "entity/source":
                    result = {"sensor.kitchen_battery": {"domain": "mobile_app"}}
                elif request_type == "get_services":
                    result = {"light": {"turn_on": {"target": {"entity": [{"domain": ["light"]}]}}}}
                elif request_type == "trace/list":
                    result = [
                        {
                            "item_id": "one",
                            "run_id": "run-1",
                            "timestamp": {"start": "2026-07-10T10:00:00+00:00"},
                            "script_execution": "error",
                            "error": "Template failed",
                        }
                    ]
                elif request_type == "automation/config":
                    result = {"config": automation_config}
                elif request_type == "trigger_platforms/subscribe":
                    await websocket.send(
                        json.dumps(
                            {
                                "id": request_id,
                                "type": "result",
                                "success": True,
                                "result": None,
                            }
                        )
                    )
                    await websocket.send(
                        json.dumps(
                            {
                                "id": request_id,
                                "type": "event",
                                "event": {
                                    "battery.became_low": {
                                        "target": {"entity": [{"device_class": ["battery"]}]}
                                    }
                                },
                            }
                        )
                    )
                    continue
                elif request_type == "condition_platforms/subscribe":
                    await websocket.send(
                        json.dumps(
                            {
                                "id": request_id,
                                "type": "event",
                                "event": {},
                            }
                        )
                    )
                    await websocket.send(
                        json.dumps(
                            {
                                "id": request_id,
                                "type": "result",
                                "success": True,
                                "result": None,
                            }
                        )
                    )
                    continue
                elif request_type == "unsubscribe_events":
                    result = None
                elif request_type == "extract_from_target":
                    resolved_targets.append(request["target"])
                    result = {
                        "referenced_entities": ["sensor.kitchen_battery"],
                        "referenced_devices": ["battery-device"],
                        "referenced_areas": ["kitchen"],
                        "missing_devices": [],
                        "missing_areas": [],
                        "missing_floors": [],
                        "missing_labels": [],
                    }
                elif request_type == "validate_config":
                    result = {
                        "triggers": {"valid": True, "error": None},
                        "actions": {"valid": True, "error": None},
                    }
                elif request_type == "trace/get":
                    result = {"trace": {"action/0": [{"template_errors": ["Undefined variable"]}]}}
                else:
                    raise AssertionError(f"Unexpected command: {request_type}")

                await websocket.send(
                    json.dumps(
                        {
                            "id": request_id,
                            "type": "result",
                            "success": True,
                            "result": result,
                        }
                    )
                )
        except ConnectionClosed:
            return

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        settings = Settings(
            websocket_url=f"ws://127.0.0.1:{port}",
            token="test-token",
            request_timeout=3,
        )
        snapshot = await HomeAssistantClient(settings).fetch_snapshot([])

    assert snapshot.home_assistant_config["version"] == "2026.7.2"
    assert snapshot.automation_configs["automation.websocket_automation"] == automation_config
    assert snapshot.device_registry[0]["id"] == "battery-device"
    assert snapshot.label_registry == []
    assert "Labels unavailable" in snapshot.warnings[0]
    key = target_key({"area_id": ["kitchen"]})
    assert snapshot.target_resolutions[key]["referenced_entities"] == ["sensor.kitchen_battery"]
    assert snapshot.target_resolutions[key]["primary_entities"] == ["sensor.kitchen_battery"]
    assert snapshot.validations["runtime:automation.websocket_automation"]["actions"]["valid"]
    assert snapshot.trace_details["one"]["trace"]["action/0"][0]["template_errors"] == [
        "Undefined variable"
    ]
    assert "unsubscribe_events" in received_types
    assert "trace/get" in received_types
    assert resolved_targets == [
        {"area_id": ["kitchen"]},
        {"area_id": ["kitchen"]},
    ]


@pytest.mark.anyio
async def test_home_assistant_client_requires_a_token() -> None:
    client = HomeAssistantClient(Settings(token=""))

    with pytest.raises(HomeAssistantConnectionError, match="TOKEN"):
        await client.fetch_snapshot([])


class ProxyBadGateway(WebSocketException):
    def __init__(self) -> None:
        super().__init__("server rejected WebSocket connection: HTTP 502")
        self.response = type("Response", (), {"status_code": 502})()


@pytest.mark.anyio
async def test_proxy_502_is_reported_as_temporary_startup_failure(monkeypatch) -> None:
    calls = 0

    def reject_connection(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise ProxyBadGateway

    async def skip_delay(_seconds: float) -> None:
        return None

    monkeypatch.setattr(ha_client_module, "connect", reject_connection)
    monkeypatch.setattr(ha_client_module.asyncio, "sleep", skip_delay)
    client = HomeAssistantClient(Settings(token="test-token"))

    with pytest.raises(HomeAssistantConnectionError, match="still starting") as raised:
        await client.fetch_snapshot([])

    assert "retry automatically" in str(raised.value)
    assert calls == 3
