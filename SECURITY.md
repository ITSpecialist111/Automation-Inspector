# Security policy

## Supported versions

Security fixes are provided for the latest 1.x release. The 0.4.x line is unsupported because it publishes sensitive Home Assistant report data on an unauthenticated host port and uses unsafe HTML rendering.

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** / private security advisory feature for this repository. Do not open a public issue containing exploit details, Home Assistant tokens, automation definitions, entity states, hostnames, or logs with secrets.

Include the affected version, impact, minimal reproduction, and any proposed mitigation. Reports will be acknowledged as soon as practical.

## Security model

- Home Assistant Ingress provides user authentication and limits the panel to administrators.
- The App receives a Supervisor token for its internal, read-only analysis calls. It never returns or logs that token.
- The configuration mount is read-only and the runtime container is unprivileged.
- The dashboard loads no third-party runtime assets and uses a nonce-based Content Security Policy.
- Local development mode does not add authentication and must not be exposed to an untrusted network.