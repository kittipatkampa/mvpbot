# TODO

Feature backlog for mvpbot.

## Features

- [ ] Support multi-user signin
- [ ] The bottom of the left menu panel should be about user and settings

## Improvements

- [x] Add Langfuse observability branch (`example/langfuse`)
- [x] Add Arize/Phoenix observability branch (`example/arize-phoenix`)
- [x] Add Logfire observability branch (`example/logfire`)
- [ ] How does thread work here? Who assigns thread_id?
- [ ] For each LLM call in the repo, we want to be flexible about what vendor and model to use, so we want to use model from [Openrouter](https://openrouter.ai/). This enable us to choose the model name in `.env`. Please build the new feature on branch (`example/openrouter`) based off from branch `main`.