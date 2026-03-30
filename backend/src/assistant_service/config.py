from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""

    # Logging — set LOG_LEVEL=DEBUG in .env to see per-chunk stream traces
    log_level: str = "INFO"
    assistant_db_path: Path = Path(__file__).resolve().parent.parent.parent / "data" / "assistant.db"

    # Classifier — fast model, no reasoning needed
    # Model IDs use OpenRouter's provider/model-name format: https://openrouter.ai/models
    classifier_model: str = "anthropic/claude-haiku-4.5"
    classifier_max_tokens: int = 1024

    # Agent — reasoning enabled to demo the "thinking" display in the UI
    agent_model: str = "anthropic/claude-sonnet-4.6"
    agent_max_tokens: int = 10_000
    # OpenRouter reasoning param — set in .env to enable thinking tokens:
    #   {"enabled": true}            — adaptive thinking for claude-sonnet-4.6 / claude-opus-4.6
    #   {"enabled": true, "max_tokens": N} — budget-based thinking (older models or explicit budget)
    #   {"effort": "high"}           — OpenAI o-series
    #   {}                           — omit reasoning param (default; required for Qwen and models
    #                                  that reason natively and reject the reasoning field)
    agent_reasoning: dict = {}

    # Arize Phoenix observability — leave empty to disable tracing
    # Self-hosted: run `python -m phoenix.server.main` and set the endpoint below
    # Cloud: set both endpoint and api_key from https://app.phoenix.arize.com
    phoenix_collector_endpoint: str = ""
    phoenix_api_key: str = ""


settings = Settings()
