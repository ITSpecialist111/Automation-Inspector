# Contributing

Contributions are welcome through focused issues and pull requests.

## Requirements

- Python 3.12 or newer (production uses 3.14)
- Node.js 24 LTS and Playwright Chromium for JavaScript and browser checks
- Docker for container validation

Install `requirements-dev.txt`, run `npm ci --ignore-scripts` and `npx playwright install chromium`, then run these checks before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
node --check automation_inspector/www/app.js
python -m pytest --cov --cov-fail-under=75
npm test
npm run test:ui
```

Browser tests use synthetic data through the real FastAPI application. They cover desktop/mobile workflows, local assets, light/dark accessibility, safe DOM rendering, and narrow-screen control sizing. After font or icon dependency updates, run `npm run assets` and include the regenerated assets and license files in the pull request.

## Design constraints

- Runtime behavior must remain read-only toward Home Assistant.
- Production access must remain authenticated through Ingress unless an equivalent application-level authentication design is supplied.
- Do not render API values through `innerHTML`, `insertAdjacentHTML`, or equivalent HTML parsing sinks.
- Preserve the strict CSP; use external static assets or an explicit per-response nonce.
- Use Home Assistant's own WebSocket APIs and target metadata rather than adding fixed domain lists.
- Missing references must remain visible even when no state exists.
- New analysis behavior needs unit or protocol-level tests.
- App version, image tag, changelog, and release must agree.

## Pull requests

Keep changes small enough to review, explain any report-schema change, add migration notes for breaking behavior, and include the Home Assistant versions used for manual testing.