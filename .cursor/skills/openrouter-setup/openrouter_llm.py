"""Custom OpenRouter chat model that preserves reasoning tokens.

The official `langchain-openrouter` SDK drops the `reasoning` field from
streaming delta chunks because its Pydantic model schema doesn't include it.
This module implements a thin LangChain-compatible wrapper that calls the
OpenRouter API directly via httpx and correctly surfaces reasoning tokens in
`additional_kwargs["reasoning_content"]`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field, SecretStr

_OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"


def _messages_to_dicts(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if isinstance(m, SystemMessage):
            out.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            out.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            msg: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            # Preserve reasoning for multi-turn
            if rc := (m.additional_kwargs or {}).get("reasoning_content"):
                msg["reasoning"] = rc
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "type": "function",
                        "id": tc["id"],
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"]),
                        },
                    }
                    for tc in m.tool_calls
                ]
            out.append(msg)
        elif isinstance(m, ToolMessage):
            out.append(
                {
                    "role": "tool",
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                }
            )
        else:
            out.append({"role": "user", "content": str(m.content)})
    return out


def _parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("data: ") or line == "data: [DONE]":
        return None
    try:
        return json.loads(line[6:])
    except json.JSONDecodeError:
        return None


def _chunk_to_generation(data: dict[str, Any]) -> ChatGenerationChunk | None:
    choices = data.get("choices")
    if not choices:
        return None
    delta = choices[0].get("delta", {})
    content = delta.get("content") or ""
    reasoning = delta.get("reasoning") or ""

    additional_kwargs: dict[str, Any] = {}
    if reasoning:
        additional_kwargs["reasoning_content"] = reasoning

    finish_reason = choices[0].get("finish_reason")
    generation_info = {"finish_reason": finish_reason} if finish_reason else None

    msg = AIMessageChunk(content=content, additional_kwargs=additional_kwargs)
    return ChatGenerationChunk(message=msg, generation_info=generation_info)


class ChatOpenRouterWithReasoning(BaseChatModel):
    """OpenRouter chat model that correctly surfaces reasoning tokens."""

    api_key: SecretStr = Field(...)
    model_name: str = Field(alias="model")
    max_tokens: int = 16_000
    reasoning: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}

    @property
    def _llm_type(self) -> str:
        return "openrouter-reasoning"

    @property
    def _default_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
        }
        if self.reasoning is not None:
            params["reasoning"] = self.reasoning
        return params

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self, messages: list[BaseMessage], stream: bool = False
    ) -> dict[str, Any]:
        return {
            **self._default_params,
            "messages": _messages_to_dicts(messages),
            "stream": stream,
        }

    # ── sync non-streaming ──────────────────────────────────────────────────

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stream=False)
        resp = httpx.post(
            _OPENROUTER_BASE, headers=self._headers(), json=payload, timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        additional_kwargs: dict[str, Any] = {}
        if reasoning := choice.get("reasoning"):
            additional_kwargs["reasoning_content"] = reasoning
        msg = AIMessage(content=content, additional_kwargs=additional_kwargs)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    # ── sync streaming ──────────────────────────────────────────────────────

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stream=True)
        with httpx.stream(
            "POST",
            _OPENROUTER_BASE,
            headers=self._headers(),
            json=payload,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                data = _parse_sse_line(line)
                if data is None:
                    continue
                gen = _chunk_to_generation(data)
                if gen is None:
                    continue
                if run_manager:
                    run_manager.on_llm_new_token(gen.text, chunk=gen)
                yield gen

    # ── async non-streaming ─────────────────────────────────────────────────

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stream=False)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                _OPENROUTER_BASE, headers=self._headers(), json=payload
            )
            resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        additional_kwargs: dict[str, Any] = {}
        if reasoning := choice.get("reasoning"):
            additional_kwargs["reasoning_content"] = reasoning
        msg = AIMessage(content=content, additional_kwargs=additional_kwargs)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    # ── async streaming ─────────────────────────────────────────────────────

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                _OPENROUTER_BASE,
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    data = _parse_sse_line(line)
                    if data is None:
                        continue
                    gen = _chunk_to_generation(data)
                    if gen is None:
                        continue
                    if run_manager:
                        await run_manager.on_llm_new_token(gen.text, chunk=gen)
                    yield gen
