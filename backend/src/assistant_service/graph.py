"""LangGraph: classify intent, route to math or general subagent."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistant_service.agents.classifier import classify_intent_text
from assistant_service.agents.general_agent import GENERAL_SYSTEM, build_general_llm
from assistant_service.agents.math_agent import MATH_SYSTEM, build_math_llm


class AssistantState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str


def _last_user_text(messages: list[BaseMessage]) -> str | None:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            c = m.content
            return c if isinstance(c, str) else str(c)
    return None


async def classify_intent(state: AssistantState) -> dict:
    text = _last_user_text(state["messages"])
    if not text:
        return {"intent": "general"}
    result = await asyncio.to_thread(classify_intent_text, text)
    return {"intent": result.intent}


def route_by_intent(state: AssistantState) -> Literal["math_agent", "general_agent"]:
    if state.get("intent") == "math":
        return "math_agent"
    return "general_agent"


async def math_agent(state: AssistantState) -> dict:
    llm = build_math_llm()
    messages: list[BaseMessage] = [SystemMessage(content=MATH_SYSTEM), *state["messages"]]
    response = await llm.ainvoke(messages)
    if not isinstance(response, AIMessage):
        response = AIMessage(content=getattr(response, "content", str(response)))
    return {"messages": [response]}


async def general_agent(state: AssistantState) -> dict:
    llm = build_general_llm()
    messages: list[BaseMessage] = [SystemMessage(content=GENERAL_SYSTEM), *state["messages"]]
    response = await llm.ainvoke(messages)
    if not isinstance(response, AIMessage):
        response = AIMessage(content=getattr(response, "content", str(response)))
    return {"messages": [response]}


def build_graph():
    g = StateGraph(AssistantState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("math_agent", math_agent)
    g.add_node("general_agent", general_agent)
    g.add_edge(START, "classify_intent")
    g.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {"math_agent": "math_agent", "general_agent": "general_agent"},
    )
    g.add_edge("math_agent", END)
    g.add_edge("general_agent", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
