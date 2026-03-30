"""Intent classifier tests (mocked LLM)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from assistant_service.agents.classifier import IntentClassification, classify_intent_text


@patch("assistant_service.agents.classifier.build_classifier_llm")
def test_classify_intent_mocked(mock_build: MagicMock):
    mock_llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = IntentClassification(intent="math")
    mock_llm.with_structured_output.return_value = structured
    mock_build.return_value = mock_llm

    assert classify_intent_text("Compute 2+2").intent == "math"


@patch("assistant_service.agents.classifier.build_classifier_llm")
def test_classify_general_mocked(mock_build: MagicMock):
    mock_llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = IntentClassification(intent="general")
    mock_llm.with_structured_output.return_value = structured
    mock_build.return_value = mock_llm

    assert classify_intent_text("Who wrote Hamlet?").intent == "general"
