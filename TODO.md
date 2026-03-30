# TODO

Feature backlog for mvpbot.

## Features

- [ ] Support multi-user signin (branch `feat/multi-user` exists; not merged to main yet)
- [ ] The bottom of the left menu panel should be about user and settings

## Improvements

- [x] Add Langfuse observability branch (`example/langfuse`)
- [x] Add Arize/Phoenix observability branch (`example/arize-phoenix`)
- [x] Add Logfire observability branch (`example/logfire`)
- [x] How does thread work here? Who assigns thread_id? — The backend assigns it: `db.create_thread()` generates a `uuid.uuid4()` if the client doesn't supply one (`main.py` line 100, `db.py` line 132).
- [x] For each LLM call in the repo, we want to be flexible about what vendor and model to use, so we want to use model from [Openrouter](https://openrouter.ai/). This enable us to choose the model name in `.env`. Please build the new feature on branch (`example/openrouter`) based off from branch `main`.