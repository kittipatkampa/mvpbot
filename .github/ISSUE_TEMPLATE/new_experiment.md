---
name: New Experiment / Observability Integration
about: Propose a new example/* branch adding an LLM observability or other integration
title: "feat: add <Tool> integration"
labels: enhancement
assignees: ""
---

## Integration Name

<!-- e.g., Weights & Biases, OpenTelemetry, Helicone -->

## Why This Integration?

<!-- What value does it bring to developers using this template? Is it self-hosted, cloud-based, free tier available? -->

## Proposed Branch Name

`example/<tool-name>`

## Required Environment Variables

| Variable | Description |
| --- | --- |
| `EXAMPLE_API_KEY` | <!-- describe --> |

## Files to Change

Per the [contributing guide](../CONTRIBUTING.md), an integration should touch only:

- [ ] `backend/src/assistant_service/observability.py` — `init_*()` function
- [ ] - [ ] `backend/src/assistant_service/config.py` — new env var settings
- [ ] - [ ] `backend/src/assistant_service/main.py` — call `init_*()` in lifespan handler
- [ ] - [ ] `backend/pyproject.toml` — add package dependency
- [ ] - [ ] `backend/.env.example` — document the env vars
- [ ] - [ ] README.md comparison table updated on `main`

- [ ] ## Opt-in Behaviour

- [ ] <!-- Confirm that if the required env var is empty, init_*() will be a no-op and the service starts normally. -->

- [ ] - [ ] Yes, tracing is fully opt-in (no env var → no-op)

- [ ] ## Additional Notes

- [ ] <!-- Links to the tool's docs, SDK, or any relevant examples. -->
