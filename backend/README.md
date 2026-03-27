# Assistant service

LangGraph + FastAPI backend. See repository root `README.md` for full setup.

---

## Langfuse observability

This branch (`example/langfuse`) adds [Langfuse](https://langfuse.com) LLM tracing on top of the base `main` branch.
Every chat request is traced as a LangChain run and appears in the Langfuse dashboard with full token counts, latency, and the classifier → subagent routing chain.

### How it works

| File | What it does |
|------|-------------|
| `src/assistant_service/observability.py` | Thin wrapper: `init_langfuse()` creates the global client; `get_langfuse_handler()` returns a `CallbackHandler` + metadata dict |
| `src/assistant_service/config.py` | Three new settings: `langfuse_public_key`, `langfuse_secret_key`, `langfuse_host` |
| `src/assistant_service/main.py` | Calls `init_langfuse()` in the FastAPI lifespan; passes the handler + metadata into `graph.astream()` config on every request |

The integration is **opt-in**: if the keys are absent the handler is `None` and no callbacks are registered — the app runs exactly as on `main`.

### Quick start

1. **Get keys** from [cloud.langfuse.com](https://cloud.langfuse.com) (US region: `us.cloud.langfuse.com`) or your self-hosted instance.

2. **Add to `backend/.env`**:

   ```dotenv
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   # Optional — defaults to https://us.cloud.langfuse.com
   LANGFUSE_HOST=https://us.cloud.langfuse.com
   ```

3. **Start the server** (no code changes needed):

   ```bash
   cd backend
   uv sync --all-extras
   uv run uvicorn assistant_service.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Send a chat message** via the UI or directly:

   ```bash
   # Create a thread
   curl -s -X POST http://localhost:8000/api/threads | jq .thread_id

   # Chat (replace <thread_id>)
   curl -s -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"thread_id":"<thread_id>","message":"What is 2+2?"}' \
     --no-buffer
   ```

5. Open your Langfuse project dashboard — the trace appears within a few seconds.

### Verifying credentials without starting the server

```python
# backend/
uv run python - <<'EOF'
import os
from dotenv import load_dotenv
load_dotenv(".env")
from langfuse import Langfuse

client = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
)
print("auth_check:", client.auth_check())  # True = keys are valid
EOF
```

### What each trace contains

- **Session ID** — set to the `thread_id` so all turns in a conversation are grouped under one Langfuse session.
- **Classifier span** — the Haiku call that picks `math` vs `general`.
- **Subagent span** — the Sonnet call (with extended thinking) that produces the answer.
- **Token usage & cost** — populated automatically by the LangChain callback.

### Running the tests

```bash
cd backend
uv run pytest tests/test_observability.py -v
```

The observability tests are fully offline (no real Langfuse calls). They cover:

| Test | What it checks |
|------|---------------|
| `test_get_langfuse_handler_returns_none_when_client_not_initialized` | No handler when client is `None` |
| `test_get_langfuse_handler_returns_none_with_empty_keys` | No handler when keys are empty strings |
| `test_init_langfuse_does_nothing_when_keys_missing` | `init_langfuse()` is a no-op without keys |
| `test_init_langfuse_creates_client_when_keys_set` | Client is created when keys are present |
| `test_get_langfuse_handler_returns_handler_when_client_initialized` | Returns a `CallbackHandler` instance |
| `test_get_langfuse_handler_includes_session_id_in_metadata` | `langfuse_session_id` key in metadata |
| `test_get_langfuse_handler_includes_user_id_in_metadata` | `langfuse_user_id` key in metadata |

Two additional integration tests in `tests/test_api.py` verify the handler is wired into the chat endpoint:

- `test_chat_passes_langfuse_callbacks_to_graph` — asserts the mock handler reaches `graph.astream()` config.
- `test_chat_omits_callbacks_when_langfuse_not_configured` — asserts an empty callbacks list when Langfuse is off.

### Disabling tracing

Remove (or leave unset) `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`. The app will start without any tracing and behave identically to the `main` branch.

### Self-hosted Langfuse

Set `LANGFUSE_HOST` to your instance URL, e.g.:

```dotenv
LANGFUSE_HOST=https://langfuse.your-company.com
```

No other changes are required.
