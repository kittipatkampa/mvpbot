"""Smoke test: send a real LangChain span to Phoenix and verify no export errors.

Usage:
    cd /Users/kittipatkampa/code/mvpbot/backend
    uv run python -m tests.test_phoenix
"""

import time

from assistant_service.config import settings
from assistant_service.observability import init_phoenix


if __name__ == "__main__":
    init_phoenix()
    print("Phoenix initialized successfully")

    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY not set — skipping LangChain call")
    else:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model=settings.classifier_model, api_key=settings.anthropic_api_key)
        response = llm.invoke("Say hello in one word")
        print(f"LangChain response: {response.content}")

        # Give the BatchSpanProcessor time to flush before exit
        print("Waiting for span export...")
        time.sleep(5)
        print("Done — check the Phoenix console for a new trace.")
