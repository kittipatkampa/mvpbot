"""Graph structure smoke test (no LLM)."""

from __future__ import annotations

from assistant_service.graph import build_graph, route_by_intent


def test_route_by_intent():
    assert route_by_intent({"intent": "math", "messages": []}) == "math_agent"
    assert route_by_intent({"intent": "general", "messages": []}) == "general_agent"


def test_graph_compiles():
    g = build_graph()
    assert g is not None
