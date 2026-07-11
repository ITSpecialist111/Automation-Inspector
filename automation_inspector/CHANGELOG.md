# Changelog

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