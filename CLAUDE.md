# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mvpbot** is a boilerplate/experimentation framework for AI chat applications. The `main` branch is a clean baseline; `example/*` branches each demonstrate a single observability integration (Logfire, Langfuse, Arize Phoenix) as a **single commit on top of main**.

## Development Commands

### Backend (Python/FastAPI)
```bash
cd backend
cp .env.example .env          # then set ANTHROPIC_API_KEY
uv sync --all-extras
uv run uvicorn assistant_service.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:
```bash
cd backend
uv run pytest tests/ -v
uv run pytest tests/test_api.py -v   # single test file
```

### Frontend (Next.js)
```bash
cd frontend
cp .env.example .env.local    # optional: set NEXT_PUBLIC_API_URL
yarn install
yarn dev                      # http://localhost:3000
```

Lint/format:
```bash
yarn lint          # check with Biome
yarn lint:fix      # auto-fix
yarn format:fix    # auto-format
```

## Architecture

The app uses **SSE streaming** from a FastAPI backend through a **LangGraph** workflow to the Anthropic API, with a **Next.js** frontend using `assistant-ui`.

```
Next.js (assistant-ui + Zustand)
    │  SSE POST /api/chat + REST /api/threads/*
FastAPI (main.py)
    │  X-Device-ID header for user scoping
LangGraph StateGraph (graph.py)
    ├── classify_intent  →  claude-haiku-4-5
    ├── math_agent       →  claude-sonnet + extended thinking
    └── general_agent    →  claude-sonnet + extended thinking
SQLite (aiosqlite) — users, threads, messages (incl. reasoning field)
```

### Backend Key Files
- `backend/src/assistant_service/main.py` — FastAPI app, all endpoints, SSE streaming logic, message persistence
- `backend/src/assistant_service/graph.py` — LangGraph StateGraph with intent-based routing
- `backend/src/assistant_service/agents/` — classifier, math_agent, general_agent
- `backend/src/assistant_service/db.py` — async SQLite CRUD (users, threads, messages)
- `backend/src/assistant_service/config.py` — Pydantic settings (model names, token budgets, log level)
- `backend/src/assistant_service/observability.py` — Logfire init + `chat_span()` context manager (no-op if token not set)

### Frontend Key Files
- `frontend/app/assistant.tsx` — main layout; wires `createFastAPIAdapter` + `useRemoteThreadListRuntime`
- `frontend/lib/fastapi-thread-runtime.tsx` — SSE parsing, optimistic UI, regenerate support
- `frontend/lib/fastapi-remote-adapter.ts` — maps `assistant-ui` thread list interface to FastAPI calls
- `frontend/lib/api.ts` — all fetch wrappers; sends `X-Device-ID` header for user scoping
- `frontend/components/assistant-ui/thread.tsx` — chat UI with reasoning collapsible + math rendering

### SSE Event Format (POST /api/chat)
```json
{"type": "reasoning", "content": "..."}   // extended thinking token
{"type": "token", "content": "..."}        // answer text token
{"type": "done"}                           // stream complete
{"type": "error", "message": "..."}        // error
```

## Key Design Decisions

- **Anonymous multi-user:** Users are scoped by `X-Device-ID` header (generated in `localStorage`). No login required.
- **Extended thinking:** Both agents use `claude-sonnet` with extended thinking; reasoning is stored in the `messages.reasoning` DB column and surfaced in the UI as a collapsible section.
- **Intent routing:** A cheap Haiku classifier decides math vs. general before the main agent runs.
- **Example branches:** Each observability integration lives on its own branch as a single commit. Use `git diff main example/<name>` to see exactly what changed.
- **Logfire:** Enabled only when `LOGFIRE_TOKEN` is set in `.env`; otherwise all observability calls are no-ops.

## Environment Variables (Backend)
| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Anthropic API key |
| `CLASSIFIER_MODEL` | `claude-haiku-4-5` | Intent classifier model |
| `AGENT_MODEL` | `claude-sonnet-4-20250514` | Main agent model |
| `AGENT_THINKING_BUDGET_TOKENS` | `10000` | Extended thinking token budget |
| `LOGFIRE_TOKEN` | (empty) | Logfire token; leave empty to disable |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
