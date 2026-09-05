# Changelog

## 1.2.0 - 2026-09-05

### Added

- Ignore and restore individual dependency findings until the automation or script configuration changes (#29). Ignores are scoped to the entity's failure status, so ignoring an unavailable sensor does not hide a later missing reference. Other validation and trace findings remain visible.
- Dedicated automation, script, ignored-finding, and helper views, with consistent filtering and counters.
- Repeatable desktop/mobile browser tests for navigation, filters, ignores, refresh recovery, caching, pagination, keyboard use, safe text rendering, responsive layouts, and light/dark accessibility. Browser and asset checks now gate container CI.

### Fixed

- Exclude script field labels, examples, and selector metadata from dependency analysis while preserving defaults and executable action data (#34).
- Parse Jinja syntax without rendering templates. Namespace attributes, loop variables, and comments no longer create false missing entities, while quoted references and state-object access remain visible (#32).
- Recognize registered services in configuration values and template literals, including legacy notify services, notify groups, and repeat lists. Explicit entity targets and state lookups still require real entities (#32, #33).
- Restrict deprecated `behavior: any` to `each` guidance to triggers. Conditions using `any` or `all` no longer receive invalid migration advice (#33).
- Correct explicit light-theme selection, preserve failure indicators while cached results remain visible, and restore normal empty-state text after recovery.
- Allow Python patch updates in the container contract while retaining the required Python and Alpine series (#35).

### Changed

- Redesign the interface with MongoDB-inspired white surfaces, deep-teal navigation, green controls, flat expandable rows, self-hosted DM Sans and Source Code Pro fonts, and Lucide icons. No CDN or external runtime assets are used.
- Update production Python to 3.14.7, FastAPI to 0.141.1, Uvicorn to 0.52.4, and websockets to 17.1. Add Jinja2 3.1.6 for syntax analysis (#35, #36).
- Update setup-python to v7 and refresh development dependencies (#30, #36).
- Keep API schema version 2 with additive `config_hash` and dependency `kind` fields. Template literals use the `template_value` reference source, distinct from explicit template entity lookups.

### Upgrade Notes

- Home Assistant 2026.7.0 or newer and authenticated Ingress remain required. No new App options or Home Assistant writes are introduced.
- Ignores are stored in the current browser, are not shared between browsers, and do not alter the API report. If browser storage is blocked, changes last only for the current page session and the interface reports that limitation.
- Browser tests use synthetic inspection data. The reported Home Assistant configurations are covered by regression tests, not a live Home Assistant validation run.

## 1.1.2 — 2026-07-28

### Changed

- Update runtime dependencies: FastAPI 0.140.7 and websockets 16.1.1.
- Update development dependencies: Ruff 0.16.0, mypy 2.3.0, anyio 4.14.2, and types-PyYAML 6.0.12.20260724.

## 1.1.1 — 2026-07-28

### Fixed

- Apply the configured App options again. Supervisor writes `/data/options.json` as root with mode `0600`, so the unprivileged container user could not read it and every option silently fell back to its built-in default. The container now stages a readable copy of the options and then drops privileges, so `refresh_interval`, `request_timeout`, `include_disabled`, `inspect_traces`, and `scan_automations_file` take effect.

## 1.1.0 — 2026-07-28

### Added

- Inspect scripts alongside automations, including their entity dependencies, target resolution, native validation, compatibility findings, and recent trace failures.
- Report script totals in the API summary (`scripts`, `inspected_items`, `items_with_issues`) and list scripts in the dependency explorer with **Edit** and **Traces** links.

### Fixed

- Stop reporting event trigger `event_type` values such as `timer.finished` as missing entities; the referenced `event_data` entity is still tracked.
- Stop scanning automation `description` prose for entity references, so notes about removed entities no longer create missing dependencies.
- Stop reporting Jinja runtime context variables such as `trigger.entity_id`, `repeat.item`, and `repeat.item.boolean` as missing entities, while still detecting real entities referenced inside templates.
- Stop listing duplicate `automations.yaml` entries produced by YAML anchors and aliases as phantom "not loaded" automations that inflated the automation count.

### Changed

- Unreferenced helper detection now also accounts for helpers used by scripts, reducing false cleanup suggestions.

## 1.0.2 — 2026-07-12

### Fixed

- Recover automatically when the Supervisor WebSocket proxy temporarily returns HTTP 502 while Home Assistant Core is starting.
- Retry every 10 seconds until the first successful inspection instead of waiting for the normal refresh interval.
- Let ordinary dashboard requests trigger a coalesced recovery when no cached inspection exists.
- Explain HTTP 502 as temporary Core/Supervisor unavailability rather than exposing a low-level WebSocket exception.

### Changed

- Start the web server and health endpoint immediately while the first Home Assistant inspection runs in the background.
- Reduce expected startup-connection log noise while retaining full diagnostics for failures after a successful snapshot.

## 1.0.1 — 2026-07-11

### Fixed

- Treat Jinja expressions in entity, device, area, floor, and label targets as runtime-resolved values instead of sending them to Home Assistant's static target API.
- Prevent templated target expressions such as `{{ sonos_speaker }}` from appearing as missing entity dependencies.
- Deduplicate repeated source warnings while preserving their original order.

### Changed

- Show dynamic targets as informational **Runtime** chips in automation details.
- Use version-tag pushes as the single release/image publication trigger to avoid duplicate builds.

## 1.0.0 — 2026-07-11

### Breaking

- Require Home Assistant 2026.7.0 or newer.
- Remove direct host-port publication; the dashboard is authenticated Ingress-only.
- Drop unsupported `armv7`; retain `amd64` and `aarch64`.
- Replace the legacy report shape with schema version 2. The old URL remains as an alias.

### Added

- Canonical automation configuration retrieval over the Home Assistant WebSocket API.
- Entity/device/area/floor/label target resolution with trigger/condition/action filtering.
- Home Assistant-native config validation and exact 2026.7 rename guidance.
- Safe read-only `automations.yaml` scan for automations that failed to load.
- Recent trace and template-error diagnostics.
- Missing, disabled, unavailable, and unknown dependency classification.
- Configurable refresh, timeout, disabled-automation, trace, and file-scan options.
- Versioned API, readiness/status endpoints, ETags, coalesced refreshes, and last-known-good data.
- Accessible responsive dashboard with safe DOM rendering and strict CSP.
- Unit, protocol, API, packaging, security, lint, type, coverage, and container CI gates.
- Signed multi-architecture GHCR release workflow.

### Changed

- Migrate Home Assistant packaging terminology and manifest layout from add-on to App.
- Upgrade to Python 3.14, current FastAPI/Uvicorn/WebSockets/PyYAML releases, and a non-root container.
- Replace the 24-hour cache with a five-minute configurable background snapshot.

### Removed

- Wildcard CORS.
- Unused Lovelace YAML renderer.
- Hardcoded entity-domain allowlist.
- Unsafe frontend HTML interpolation.