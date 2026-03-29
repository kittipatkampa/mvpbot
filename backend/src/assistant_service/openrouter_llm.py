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
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field, SecretStr

_OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"


def _messages_to_dicts(messages: list[BaseMessage | dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        # Pass plain dicts through unchanged (e.g. from classifier)
        if isinstance(m, dict):
            out.append(m)
        elif isinstance(m, SystemMessage):
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
    def _identifying_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "vendor": self.model_name.split("/")[0] if "/" in self.model_name else "openrouter",
        }
        if self.reasoning is not None:
            params["reasoning"] = self.reasoning
        return params

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

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable:
        """Return a runnable that parses the model output into the given Pydantic schema.

        Uses OpenRouter's JSON response format to constrain output, then parses with
        the Pydantic model. Only supports Pydantic BaseModel subclasses.
        """
        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise ValueError("with_structured_output only supports Pydantic BaseModel subclasses")

        pydantic_schema: type[BaseModel] = schema
        headers = self._headers()
        model_name = self.model_name
        max_tokens = self.max_tokens

        from langchain_core.runnables import RunnableLambda

        def parse(messages: Any) -> BaseModel:
            if isinstance(messages, str):
                msgs: list[Any] = [HumanMessage(content=messages)]
            elif isinstance(messages, list):
                msgs = messages
            else:
                msgs = [HumanMessage(content=str(messages))]

            payload: dict[str, Any] = {
                "model": model_name,
                "max_tokens": max_tokens,
                "messages": _messages_to_dicts(msgs),
                "stream": False,
                "response_format": {"type": "json_object"},
            }
            resp = httpx.post(
                _OPENROUTER_BASE,
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"].get("content") or "{}"
            # Strip markdown code fences if the model wraps JSON in ```json ... ```
            content = content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                # Remove first line (```json or ```) and last line (```)
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else "{}"
            # Extract only the first valid JSON object/array, ignoring any
            # trailing text the model may append after the closing brace.
            try:
                obj, _ = json.JSONDecoder().raw_decode(content.strip())
                content = json.dumps(obj)
            except json.JSONDecodeError:
                pass
            return pydantic_schema.model_validate_json(content)

        return RunnableLambda(parse)

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
