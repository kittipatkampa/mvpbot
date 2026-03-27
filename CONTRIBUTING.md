# Contributing

## Branch conventions

### `main`

The clean base — no observability, no extra dependencies. This is what developers clone as a starting point. Keep it minimal.

### `example/*` branches

Each `example/<tool>` branch adds exactly **one commit** on top of `main` demonstrating a specific integration. The rule:

- Branch from `main`, never from another `example/*` branch
- One commit only — the diff must show only the integration code
- Never merge back into `main`
- Rebase (not merge) onto `main` when the base app changes:
  ```bash
  git checkout example/logfire
  git rebase main
  git push --force-with-lease origin example/logfire
  ```

### Adding a new observability integration

1. Branch from current `main`:
   ```bash
   git checkout -b example/<tool> main
   ```
2. Add only the files needed for the integration:
   - `backend/src/assistant_service/observability.py` — init function
   - `backend/src/assistant_service/config.py` — new env var settings
   - `backend/src/assistant_service/main.py` — call `init_*()` in the lifespan handler
   - `backend/pyproject.toml` — add the package dependency
   - `backend/.env.example` — document the env vars
3. Make tracing **opt-in**: if the required env var is empty, `init_*()` should be a no-op.
4. Commit everything as a single commit with a clear message, e.g.:
   ```
   feat: add <Tool> LLM observability integration
   ```
5. Update the comparison table in `README.md` on `main`.

## Running locally

See [README.md](README.md) for setup instructions.
