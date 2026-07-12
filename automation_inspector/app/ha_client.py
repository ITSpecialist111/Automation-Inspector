"""Modern Home Assistant WebSocket API client used by Automation Inspector."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from app import APP_VERSION
from app.automation_file import FileAutomation
from app.references import iter_target_uses
from app.settings import Settings

LOG = logging.getLogger(__name__)


class HomeAssistantConnectionError(RuntimeError):
    """Raised when a Home Assistant snapshot cannot be retrieved."""


def _connection_error_message(error: Exception | None) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 502:
        return (
            "Home Assistant is still starting or temporarily unavailable "
            "(Supervisor WebSocket proxy returned HTTP 502). "
            "Automation Inspector will retry automatically."
        )
    if status_code in {401, 403}:
        return (
            "Home Assistant rejected Automation Inspector API access "
            f"(HTTP {status_code}). Restart or reinstall the App to refresh its permissions."
        )
    return f"Unable to connect to Home Assistant: {error}"


@dataclass(frozen=True, slots=True)
class CommandResult:
    success: bool
    result: Any = None
    error: str | None = None


@dataclass(slots=True)
class SourceSnapshot:
    states: list[dict[str, Any]]
    home_assistant_config: dict[str, Any]
    automation_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    automation_config_errors: dict[str, str] = field(default_factory=dict)
    file_automations: list[FileAutomation] = field(default_factory=list)
    entity_registry: list[dict[str, Any]] = field(default_factory=list)
    device_registry: list[dict[str, Any]] = field(default_factory=list)
    area_registry: list[dict[str, Any]] = field(default_factory=list)
    floor_registry: list[dict[str, Any]] = field(default_factory=list)
    label_registry: list[dict[str, Any]] = field(default_factory=list)
    entity_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    trigger_descriptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    condition_descriptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    service_descriptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    target_resolutions: dict[str, dict[str, Any]] = field(default_factory=dict)
    validations: dict[str, dict[str, Any]] = field(default_factory=dict)
    traces: list[dict[str, Any]] = field(default_factory=list)
    trace_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _error_text(message: Mapping[str, Any]) -> str:
    error = message.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        text = error.get("message", "Unknown Home Assistant error")
        return f"{code}: {text}" if code else str(text)
    return str(error or "Unknown Home Assistant error")


class _Session:
    def __init__(self, websocket: ClientConnection, timeout: int) -> None:
        self.websocket = websocket
        self.timeout = timeout
        self.next_id = 1

    async def _receive(self) -> dict[str, Any]:
        raw = await asyncio.wait_for(self.websocket.recv(), timeout=self.timeout)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        message = json.loads(raw)
        if not isinstance(message, dict):
            raise HomeAssistantConnectionError("Home Assistant sent a non-object message")
        return message

    async def authenticate(self, token: str) -> None:
        message = await self._receive()
        if message.get("type") != "auth_required":
            raise HomeAssistantConnectionError(
                f"Expected auth_required, received {message.get('type')!r}"
            )
        await self.websocket.send(json.dumps({"type": "auth", "access_token": token}))
        response = await self._receive()
        if response.get("type") != "auth_ok":
            raise HomeAssistantConnectionError(
                str(response.get("message", "Home Assistant authentication failed"))
            )

    def _allocate_id(self) -> int:
        message_id = self.next_id
        self.next_id += 1
        return message_id

    async def call(self, request: Mapping[str, Any]) -> CommandResult:
        return (await self.call_many({"request": request}))["request"]

    async def call_many(
        self, requests: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, CommandResult]:
        pending: dict[int, str] = {}
        for name, request in requests.items():
            message_id = self._allocate_id()
            pending[message_id] = name
            message = dict(request)
            message["id"] = message_id
            await self.websocket.send(json.dumps(message, separators=(",", ":")))

        results: dict[str, CommandResult] = {}
        while pending:
            message = await self._receive()
            response_id = message.get("id")
            if not isinstance(response_id, int) or response_id not in pending:
                continue
            if message.get("type") != "result":
                continue
            name = pending.pop(response_id)
            if message.get("success") is True:
                results[name] = CommandResult(True, message.get("result"))
            else:
                results[name] = CommandResult(False, error=_error_text(message))
        return results

    async def subscription_snapshot(self, subscription_type: str) -> CommandResult:
        subscription_id = self._allocate_id()
        await self.websocket.send(json.dumps({"id": subscription_id, "type": subscription_type}))
        acknowledged = False
        event: Any = None
        while not acknowledged or event is None:
            message = await self._receive()
            if message.get("id") != subscription_id:
                continue
            if message.get("type") == "result":
                if message.get("success") is not True:
                    return CommandResult(False, error=_error_text(message))
                acknowledged = True
            elif message.get("type") == "event":
                event = message.get("event")

        unsubscribe = await self.call(
            {"type": "unsubscribe_events", "subscription": subscription_id}
        )
        if not unsubscribe.success:
            LOG.debug("Unable to unsubscribe from %s: %s", subscription_type, unsubscribe.error)
        return CommandResult(True, event)


def _list_result(
    results: Mapping[str, CommandResult], name: str, warnings: list[str]
) -> list[dict[str, Any]]:
    response = results.get(name)
    if response and response.success and isinstance(response.result, list):
        return [item for item in response.result if isinstance(item, dict)]
    if response and response.error:
        warnings.append(f"{name.replace('_', ' ').title()} unavailable: {response.error}")
    return []


def _dict_result(
    results: Mapping[str, CommandResult], name: str, warnings: list[str]
) -> dict[str, Any]:
    response = results.get(name)
    if response and response.success and isinstance(response.result, dict):
        return response.result
    if response and response.error:
        warnings.append(f"{name.replace('_', ' ').title()} unavailable: {response.error}")
    return {}


def _validation_request(config: Mapping[str, Any]) -> dict[str, Any] | None:
    request: dict[str, Any] = {"type": "validate_config"}
    for plural, singular in (
        ("triggers", "trigger"),
        ("conditions", "condition"),
        ("actions", "action"),
    ):
        value = config.get(plural, config.get(singular))
        if value is not None:
            request[plural] = value
    return request if len(request) > 1 else None


def _latest_traces(traces: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for trace in traces:
        if trace.get("not_triggered"):
            continue
        item_id = trace.get("item_id")
        timestamp = trace.get("timestamp")
        if not isinstance(item_id, str) or not isinstance(timestamp, dict):
            continue
        start = str(timestamp.get("start", ""))
        previous = latest.get(item_id)
        previous_start = str((previous or {}).get("timestamp", {}).get("start", ""))
        if previous is None or start > previous_start:
            latest[item_id] = trace
    return latest


async def _call_in_batches(
    session: _Session,
    requests: Mapping[str, Mapping[str, Any]],
    batch_size: int = 100,
) -> dict[str, CommandResult]:
    """Send large command sets in bounded batches to protect Home Assistant."""
    items = list(requests.items())
    results: dict[str, CommandResult] = {}
    for offset in range(0, len(items), batch_size):
        results.update(await session.call_many(dict(items[offset : offset + batch_size])))
    return results


class HomeAssistantClient:
    """Fetch one internally consistent inspection snapshot from Home Assistant."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_snapshot(self, file_automations: list[FileAutomation]) -> SourceSnapshot:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await self._fetch_once(file_automations)
            except (OSError, TimeoutError, WebSocketException, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.25 * (2**attempt))
        raise HomeAssistantConnectionError(_connection_error_message(last_error)) from last_error

    async def _fetch_once(self, file_automations: list[FileAutomation]) -> SourceSnapshot:
        if not self.settings.token:
            raise HomeAssistantConnectionError(
                "SUPERVISOR_TOKEN or HA_TOKEN is required to inspect Home Assistant"
            )

        async with connect(
            self.settings.websocket_url,
            open_timeout=self.settings.request_timeout,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            max_size=self.settings.websocket_max_size,
            compression="deflate",
            proxy=None,
            additional_headers={"User-Agent": f"Automation-Inspector/{APP_VERSION}"},
        ) as websocket:
            session = _Session(websocket, self.settings.request_timeout)
            await session.authenticate(self.settings.token)
            warnings: list[str] = []

            base_results = await session.call_many(
                {
                    "states": {"type": "get_states"},
                    "home_assistant_config": {"type": "get_config"},
                    "entity_registry": {"type": "config/entity_registry/list"},
                    "device_registry": {"type": "config/device_registry/list"},
                    "area_registry": {"type": "config/area_registry/list"},
                    "floor_registry": {"type": "config/floor_registry/list"},
                    "label_registry": {"type": "config/label_registry/list"},
                    "entity_sources": {"type": "entity/source"},
                    "services": {"type": "get_services"},
                    "traces": {"type": "trace/list", "domain": "automation"},
                }
            )

            states_response = base_results["states"]
            config_response = base_results["home_assistant_config"]
            if not states_response.success or not isinstance(states_response.result, list):
                raise HomeAssistantConnectionError(
                    f"Unable to retrieve Home Assistant states: {states_response.error}"
                )
            if not config_response.success or not isinstance(config_response.result, dict):
                raise HomeAssistantConnectionError(
                    f"Unable to retrieve Home Assistant config: {config_response.error}"
                )

            states = [item for item in states_response.result if isinstance(item, dict)]
            automation_ids = sorted(
                str(item["entity_id"])
                for item in states
                if str(item.get("entity_id", "")).startswith("automation.")
            )
            config_results = await _call_in_batches(
                session,
                {
                    entity_id: {"type": "automation/config", "entity_id": entity_id}
                    for entity_id in automation_ids
                },
            )
            automation_configs: dict[str, dict[str, Any]] = {}
            automation_config_errors: dict[str, str] = {}
            for entity_id, response in config_results.items():
                result = response.result
                config = result.get("config") if isinstance(result, dict) else None
                if response.success and isinstance(config, dict):
                    automation_configs[entity_id] = config
                else:
                    automation_config_errors[entity_id] = response.error or "Config unavailable"

            trigger_snapshot = await session.subscription_snapshot("trigger_platforms/subscribe")
            condition_snapshot = await session.subscription_snapshot(
                "condition_platforms/subscribe"
            )
            trigger_descriptions = (
                trigger_snapshot.result
                if trigger_snapshot.success and isinstance(trigger_snapshot.result, dict)
                else {}
            )
            condition_descriptions = (
                condition_snapshot.result
                if condition_snapshot.success and isinstance(condition_snapshot.result, dict)
                else {}
            )
            if not trigger_snapshot.success:
                warnings.append(f"Trigger descriptions unavailable: {trigger_snapshot.error}")
            if not condition_snapshot.success:
                warnings.append(f"Condition descriptions unavailable: {condition_snapshot.error}")

            configs_for_analysis: dict[str, dict[str, Any]] = {
                f"runtime:{entity_id}": config for entity_id, config in automation_configs.items()
            }
            configs_for_analysis.update(
                {automation.key: automation.config for automation in file_automations}
            )

            targets: dict[str, dict[str, list[str]]] = {}
            for config in configs_for_analysis.values():
                for use in iter_target_uses(config):
                    if use.target:
                        targets.setdefault(use.key, use.target)

            detail_requests: dict[str, dict[str, Any]] = {}
            for key, target in targets.items():
                detail_requests[f"target_all:{key}"] = {
                    "type": "extract_from_target",
                    "target": target,
                    "expand_group": True,
                    "primary_entities_only": False,
                }
                detail_requests[f"target_primary:{key}"] = {
                    "type": "extract_from_target",
                    "target": target,
                    "expand_group": True,
                    "primary_entities_only": True,
                }
            for key, config in configs_for_analysis.items():
                request = _validation_request(config)
                if request:
                    detail_requests[f"validation:{key}"] = request

            traces = _list_result(base_results, "traces", warnings)
            latest_traces = _latest_traces(traces)
            if self.settings.inspect_traces:
                for item_id, trace in latest_traces.items():
                    if trace.get("script_execution") not in {
                        "error",
                        "aborted",
                        "failed_max_runs",
                    } and not trace.get("error"):
                        continue
                    run_id = trace.get("run_id")
                    if isinstance(run_id, str):
                        detail_requests[f"trace:{item_id}"] = {
                            "type": "trace/get",
                            "domain": "automation",
                            "item_id": item_id,
                            "run_id": run_id,
                        }

            detail_results = (
                await _call_in_batches(session, detail_requests) if detail_requests else {}
            )

            target_resolutions: dict[str, dict[str, Any]] = {}
            primary_target_entities: dict[str, list[str]] = {}
            validations: dict[str, dict[str, Any]] = {}
            trace_details: dict[str, dict[str, Any]] = {}
            for name, response in detail_results.items():
                if not response.success or not isinstance(response.result, dict):
                    if name.startswith(("target_all:", "target_primary:")):
                        warnings.append(f"Target resolution failed: {response.error}")
                    continue
                if name.startswith("target_all:"):
                    target_resolutions[name.removeprefix("target_all:")] = response.result
                elif name.startswith("target_primary:"):
                    key = name.removeprefix("target_primary:")
                    entities = response.result.get("referenced_entities", [])
                    primary_target_entities[key] = [
                        entity_id for entity_id in entities if isinstance(entity_id, str)
                    ]
                elif name.startswith("validation:"):
                    validations[name.removeprefix("validation:")] = response.result
                elif name.startswith("trace:"):
                    trace_details[name.removeprefix("trace:")] = response.result

            for key, entities in primary_target_entities.items():
                target_resolutions.setdefault(key, {})["primary_entities"] = entities

            return SourceSnapshot(
                states=states,
                home_assistant_config=config_response.result,
                automation_configs=automation_configs,
                automation_config_errors=automation_config_errors,
                file_automations=file_automations,
                entity_registry=_list_result(base_results, "entity_registry", warnings),
                device_registry=_list_result(base_results, "device_registry", warnings),
                area_registry=_list_result(base_results, "area_registry", warnings),
                floor_registry=_list_result(base_results, "floor_registry", warnings),
                label_registry=_list_result(base_results, "label_registry", warnings),
                entity_sources=_dict_result(base_results, "entity_sources", warnings),
                trigger_descriptions=trigger_descriptions,
                condition_descriptions=condition_descriptions,
                service_descriptions=_dict_result(base_results, "services", warnings),
                target_resolutions=target_resolutions,
                validations=validations,
                traces=traces,
                trace_details=trace_details,
                warnings=list(dict.fromkeys(warnings)),
            )
