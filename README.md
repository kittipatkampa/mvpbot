# mvpbot

This repo exists for **experimentation**. Rather than starting from scratch every time you want to try something new, you can branch off a working baseline and focus on what you actually want to explore — saving hours of boilerplate setup.

The boilerplate here is built around two deliberate choices:

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** as the orchestration layer — flexible graph-based agent workflows that scale from simple routing to complex multi-agent systems.
- **[assistant-ui](https://www.assistant-ui.com/)** as the frontend — a high-quality, flexible React component library purpose-built for AI chat interfaces.

At the moment, you can experiment with **LLM observability**: each `example/*` branch drops in a different tracing tool ([Langfuse](https://langfuse.com), [Arize Phoenix](https://phoenix.arize.com), [Logfire](https://logfire.pydantic.dev)) with a single commit, so you can compare them side-by-side without any noise. See the [LLM Observability](#llm-observability) section for details.

Contributions of new experiment branches are very welcome!

---

Demo AI assistant: **LangGraph** intent routing + **FastAPI** SSE backend, and a **Next.js** UI built with **assistant-ui** (threads, search, reasoning display).

```mermaid
flowchart LR
  UI[Next.js assistant-ui] -->|SSE POST /api/chat| API[FastAPI]
  API --> LG[LangGraph]
  LG --> C[Intent classifier]
  C -->|math| M[Math agent]
  C -->|general| G[General agent]
  API --> DB[(SQLite)]
```

## Repository layout

| Path | Description |
|------|-------------|
| [`backend/`](backend/) | Python package `assistant-service`: LangGraph graph, Anthropic models, FastAPI, SQLite |
| [`frontend/`](frontend/) | Next.js app: `useRemoteThreadListRuntime` + `useExternalStoreRuntime`, SSE client |

## Prerequisites

- Python 3.11+ with [uv](https://github.com/astral-sh/uv)
- Node.js 20+ with Yarn (or use `npx` / `npm` as you prefer)
- [Anthropic API key](https://console.anthropic.com/)

## Backend (assistant service)

```bash
cd backend
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

uv sync --all-extras
uv run uvicorn assistant_service.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://localhost:8000/health`
- SQLite file (default): `backend/data/assistant.db`

### Tests

```bash
cd backend
uv run pytest tests/ -v
```

## Frontend

```bash
cd frontend
cp .env.example .env.local
# Optional: NEXT_PUBLIC_API_URL=http://localhost:8000

yarn install
yarn dev
```

Open [http://localhost:3000](http://localhost:3000).

## API (for other clients)

Base URL: `http://localhost:8000` (set `NEXT_PUBLIC_API_URL` in the frontend).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `POST` | `/api/threads` | Create thread; body optional `{"id": "<uuid>"}` for client-generated id |
| `GET` | `/api/threads` | List threads; `?q=` search, `include_archived=true` |
| `GET` | `/api/threads/{id}` | Thread metadata |
| `PATCH` | `/api/threads/{id}` | Body: `title`, `archived` |
| `DELETE` | `/api/threads/{id}` | Delete thread and messages |
| `GET` | `/api/threads/{id}/messages` | List messages (`content`, `reasoning` for assistant) |
| `POST` | `/api/chat` | **SSE** stream; body `{"thread_id", "message"}` |

### SSE events (`POST /api/chat`)

Each line is `data: <json>`:

- `{"type": "reasoning", "content": "..."}` — extended thinking token (Anthropic → LangChain `reasoning` blocks)
- `{"type": "token", "content": "..."}` — assistant answer text
- `{"type": "done"}` — stream finished
- `{"type": "error", "message": "..."}` — error

## Behavior

1. **Classifier** (`claude-haiku-4-5`) picks `math` vs `general` (see [Anthropic models](https://docs.anthropic.com/en/docs/about-claude/models/overview)).
2. **Subagents** (`claude-sonnet-4-20250514`) use Anthropic **extended thinking**; reasoning is streamed separately from the answer for the UI.

## LLM Observability

This repo ships a clean base with **no observability** on `main`. Use one of the `example/*` branches to add a tracing layer without touching any other code:

| Branch | Tool | Self-hosted? | Free tier? | Env vars required |
|--------|------|:---:|:---:|-------------------|
| `main` | None (base template) | — | — | — |
| [`example/langfuse`](../../tree/example/langfuse) | [Langfuse](https://langfuse.com) | ✅ | ✅ | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| [`example/logfire`](../../tree/example/logfire) | [Logfire](https://logfire.pydantic.dev) | ❌ | ✅ | `LOGFIRE_TOKEN` |
| [`example/arize-phoenix`](../../tree/example/arize-phoenix) | [Arize Phoenix](https://phoenix.arize.com) | ✅ | ✅ | `PHOENIX_COLLECTOR_ENDPOINT` |

Each branch adds exactly **one commit** on top of `main`. To see what an integration requires:

```bash
git diff main example/langfuse
```

To start from an integration branch:

```bash
git checkout example/logfire
# Set the relevant env vars in backend/.env, then run normally
```

## License

MIT — see [LICENSE](LICENSE).
