# Automation Inspector App documentation

Automation Inspector performs read-only health analysis of Home Assistant automations. Open it from the Home Assistant sidebar after starting the App.

## Configuration

| Option | Default | Description |
|---|---:|---|
| `refresh_interval` | 300 | Seconds between background inspections |
| `request_timeout` | 15 | Timeout for each WebSocket response |
| `include_disabled` | `true` | Analyze automations that are turned off |
| `inspect_traces` | `true` | Retrieve details for recent failed traces |
| `scan_automations_file` | `true` | Find UI-managed automations that did not load |

Restart the App after changing options.

## Reading the report

- **Missing** — no current state or registry entry exists for an explicit reference.
- **Disabled** — the entity still exists in the registry but is disabled.
- **Unavailable / unknown** — Home Assistant has a state object, but its current state is unhealthy.
- **Not loaded** — the automation exists in `automations.yaml` but has no runtime automation entity.
- **Unresolved target** — a referenced device, area, floor, or label no longer exists.
- **Runtime target** — a Jinja template such as `{{ sonos_speaker }}` that Home Assistant resolves only when the automation runs; this is informational, not a failure.
- **Compatibility** — Home Assistant validation failed or the configuration uses a removed/deprecated construct.
- **Trace failure** — the latest retained execution ended in an error or contains template errors.

Select **Inspection details** to see dependency sources, target expansion, validation findings, replacements, and trace notes. **Edit** and **Traces** open the corresponding Home Assistant page.

## Troubleshooting

### Inspection unavailable

Home Assistant may still be starting, or its WebSocket API may be unavailable. Check the App log and wait for an automatic retry. `/ready` returns 503 until the first successful snapshot.

An HTTP 502 from the Supervisor WebSocket proxy means Supervisor could not reach the Home Assistant Core API at that moment. Automation Inspector retries every 10 seconds until it succeeds. If the error persists after Home Assistant has fully started, restart Home Assistant and then restart the App; persistent 502 responses indicate a Core/Supervisor connectivity problem rather than an automation configuration problem.

### Last-known-good inspection

The current refresh failed, but an older successful report remains visible. The banner and API status identify this state. Check Home Assistant connectivity and run another inspection.

### High resource usage

Increase `refresh_interval`, disable recent trace inspection, or disable the `automations.yaml` scan. Manual refreshes are coalesced, so repeated clicks do not create parallel scans.

### Direct port no longer works

This is intentional in 1.0.0. Automation definitions and entity states are sensitive; use authenticated Home Assistant Ingress via **Open Web UI** or the sidebar.

### Unreferenced helper appears in use elsewhere

The helper list considers automations only. Scripts, dashboards, integrations, templates, and external clients are outside its scope. Always verify before deleting a helper.

## Data handling

The App does not send telemetry or Home Assistant data externally. Its only external network activity is the image pull during installation/update. Runtime analysis communicates with Home Assistant over the Supervisor's internal network.