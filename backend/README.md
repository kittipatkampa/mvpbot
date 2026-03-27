# Assistant service

LangGraph + FastAPI backend. See repository root `README.md` for full setup.

---

## Logfire observability

[Logfire](https://logfire.pydantic.dev) is the built-in tracing layer for this service. It uses OpenTelemetry under the hood and auto-instruments every Anthropic API call, so you get full LLM traces (prompts, completions, token counts, latency) with zero manual instrumentation in your agent code.

### How it works

| File | Role |
|------|------|
| `src/assistant_service/observability.py` | `init_logfire()` — configures Logfire and calls `logfire.instrument_anthropic()` |
| `src/assistant_service/config.py` | Reads `LOGFIRE_TOKEN` from the environment via `pydantic-settings` |
| `src/assistant_service/main.py` | Calls `init_logfire()` once inside the FastAPI `lifespan` handler |

`init_logfire()` is intentionally a **no-op** when `LOGFIRE_TOKEN` is empty, so the service starts cleanly in local dev or CI without any tracing configured.

### Enabling tracing

1. Create a free project at <https://logfire.pydantic.dev> and copy your write token.

2. Add the token to `backend/.env`:

   ```
   LOGFIRE_TOKEN=pylf_v1_us_<your-token-here>
   ```

3. Start (or restart) the backend:

   ```bash
   cd backend
   uv run uvicorn assistant_service.main:app --reload --host 0.0.0.0 --port 8000
   ```

   On startup you will see a line like:

   ```
   Logfire project URL: https://logfire-us.pydantic.dev/<org>/<project>
   ```

   Open that URL to view live traces.

### Disabling tracing

Leave `LOGFIRE_TOKEN` unset (or set it to an empty string). The service starts normally with no tracing overhead.

### Adding custom spans

Import `logfire` anywhere in the service and use it directly:

```python
import logfire

# Structured log at INFO level
logfire.info("Processing request", thread_id=thread_id)

# Span wrapping a block of work
with logfire.span("my-operation", param=value):
    ...

# Other log levels
logfire.debug("...")
logfire.warn("...")
logfire.error("...")
```

All built-in log levels and span types are documented at <https://logfire.pydantic.dev/docs/>.

### Running the tests

The `tests/test_logfire.py` suite uses the `capfire` pytest fixture provided by the `logfire` package itself (registered automatically via the `logfire` pytest plugin). No real token is needed — tests run fully offline.

```bash
cd backend
uv run python -m pytest tests/test_logfire.py -v
```

Expected output:

```
tests/test_logfire.py::test_logfire_info_emits_span PASSED
tests/test_logfire.py::test_init_logfire_noop_without_token PASSED
tests/test_logfire.py::test_init_logfire_configures_when_token_set PASSED
```

The three tests cover:

| Test | What it verifies |
|------|-----------------|
| `test_logfire_info_emits_span` | `logfire.info()` emits a span that the in-memory exporter captures |
| `test_init_logfire_noop_without_token` | `init_logfire()` skips `logfire.configure()` when `LOGFIRE_TOKEN` is empty |
| `test_init_logfire_configures_when_token_set` | `init_logfire()` calls `logfire.configure(token=…)` and `logfire.instrument_anthropic()` when a token is present |

### Dependency

`logfire>=3.0.0` is listed as a **production** dependency in `pyproject.toml`. No extra install step is required.
