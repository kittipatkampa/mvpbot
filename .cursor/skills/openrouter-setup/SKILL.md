---
name: openrouter-setup
description: Install, configure, and debug OpenRouter as an LLM provider in Python projects. Covers API key setup, LangChain integration, reasoning/thinking tokens, streaming (SSE), tool calling, and common failure modes. Use when the user wants to use OpenRouter, integrate it with LangChain, enable model reasoning/thinking, stream responses, or debug OpenRouter API errors.
---

# OpenRouter Setup & Integration

## What is OpenRouter

OpenRouter is a unified API gateway to 200+ LLMs (Anthropic, OpenAI, Google, Meta, etc.) using a single API key and OpenAI-compatible endpoint. Model IDs use the format `provider/model-name` (e.g. `anthropic/claude-sonnet-4.6`). Browse models at https://openrouter.ai/models.

---

## 1. Install

```bash
# Minimal: direct httpx calls (recommended for reasoning token support)
pip install httpx pydantic

# With LangChain
pip install langchain-core langchain-openrouter httpx pydantic pydantic-settings
```

---

## 2. API Key

Get a key at https://openrouter.ai/keys. Store it in `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Load with pydantic-settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str = ""
    agent_model: str = "anthropic/claude-sonnet-4.6"
    agent_max_tokens: int = 10_000
    agent_reasoning: dict = {"enabled": True}

settings = Settings(_env_file=".env")
```

---

## 3. Quick test (raw httpx)

```python
import httpx, os

resp = httpx.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
    json={
        "model": "anthropic/claude-haiku-4.5",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 256,
    },
    timeout=30,
)
resp.raise_for_status()
print(resp.json()["choices"][0]["message"]["content"])
```

---

## 4. LangChain integration

### Option A — `langchain-openrouter` (simple, no reasoning tokens)

```python
from langchain_openrouter import ChatOpenRouter

llm = ChatOpenRouter(
    model="anthropic/claude-haiku-4.5",
    openrouter_api_key="sk-or-...",
)
response = llm.invoke("Hello")
```

**Limitation**: the official SDK drops the `reasoning` field from streaming chunks. Use Option B if you need reasoning tokens.

### Option B — Custom wrapper (reasoning-safe, recommended)

See [openrouter_llm.py](openrouter_llm.py) for the full implementation. Key points:

- Subclasses `BaseChatModel`
- Calls the API directly via `httpx`
- Surfaces reasoning tokens in `additional_kwargs["reasoning_content"]`
- Supports sync/async, streaming/non-streaming, and tool calls

```python
from openrouter_llm import ChatOpenRouterWithReasoning

llm = ChatOpenRouterWithReasoning(
    model="anthropic/claude-sonnet-4.6",
    api_key="sk-or-...",
    max_tokens=10_000,
    reasoning={"enabled": True},   # or None to disable
)
response = llm.invoke("Explain quantum entanglement")
print(response.content)
print(response.additional_kwargs.get("reasoning_content"))  # thinking tokens
```

---

## 5. Reasoning / thinking tokens

OpenRouter exposes model reasoning via the `reasoning` parameter in the request body. The field returned in the response is `choices[0].delta.reasoning` (streaming) or `choices[0].message.reasoning` (non-streaming).

```python
# Adaptive thinking (claude-sonnet-4.6 / claude-opus-4.6 and newer)
reasoning = {"enabled": True}

# Budget-based thinking (claude-3.7-sonnet or explicit budget)
reasoning = {"max_tokens": 10_000}

# OpenAI o-series
reasoning = {"effort": "high"}   # "low" | "medium" | "high"

# Disable
reasoning = None  # or omit the field entirely
```

**Critical**: `langchain-openrouter`'s Pydantic schema does not include `reasoning` in delta chunks, so streaming reasoning tokens are silently dropped. Use the custom wrapper or parse SSE manually.

---

## 6. Streaming (SSE)

```python
import httpx, json

def parse_sse(line: str) -> dict | None:
    if not line.startswith("data: ") or line == "data: [DONE]":
        return None
    try:
        return json.loads(line[6:])
    except json.JSONDecodeError:
        return None

with httpx.stream("POST", "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": model, "messages": messages, "stream": True, "max_tokens": 1024},
    timeout=120,
) as resp:
    resp.raise_for_status()
    for line in resp.iter_lines():
        data = parse_sse(line)
        if data is None:
            continue
        delta = data["choices"][0].get("delta", {})
        if text := delta.get("content"):
            print(text, end="", flush=True)
        if reasoning := delta.get("reasoning"):
            print(f"[thinking: {reasoning}]", end="", flush=True)
```

---

## 7. Tool / function calling

Pass tools in OpenAI format. OpenRouter routes them to the model unchanged:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]

resp = httpx.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": model, "messages": messages, "tools": tools, "max_tokens": 1024},
    timeout=60,
)
choice = resp.json()["choices"][0]["message"]
if choice.get("tool_calls"):
    for tc in choice["tool_calls"]:
        print(tc["function"]["name"], json.loads(tc["function"]["arguments"]))
```

When serializing an `AIMessage` back into the conversation for multi-turn tool use, include `tool_calls` in the assistant message and follow up with `role: "tool"` messages.

---

## 8. Multi-turn conversation with reasoning

When replaying an `AIMessage` that had reasoning, pass the reasoning back so the model has full context:

```python
# assistant turn with reasoning preserved
{
    "role": "assistant",
    "content": "...",
    "reasoning": "<thinking>...</thinking>",  # from additional_kwargs["reasoning_content"]
}
```

---

## 9. Debugging

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `401 Unauthorized` | Wrong or missing API key | Check `OPENROUTER_API_KEY` in `.env`; key starts with `sk-or-` |
| `404 Not Found` | Wrong model ID | Check exact ID at https://openrouter.ai/models |
| `402 Payment Required` | Insufficient credits | Top up at https://openrouter.ai/credits |
| `429 Too Many Requests` | Rate limit | Add retry with exponential backoff |
| Reasoning tokens missing in stream | `langchain-openrouter` drops them | Use custom `ChatOpenRouterWithReasoning` wrapper |
| Empty `content` in response | Model used tool call or only reasoned | Check `tool_calls` field; reasoning models may return empty `content` |
| Timeout on long reasoning | Default timeout too short | Set `timeout=120` or higher in httpx |
| `stream=True` but no chunks | Missing `Accept: text/event-stream` header | httpx handles this automatically; check proxy/firewall |

Enable debug logging to trace per-chunk SSE output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set `LOG_LEVEL=DEBUG` in `.env` if using pydantic-settings.

---

## Additional resources

- Full custom LangChain wrapper: [openrouter_llm.py](openrouter_llm.py)
- OpenRouter model list: https://openrouter.ai/models
- OpenRouter API docs: https://openrouter.ai/docs
