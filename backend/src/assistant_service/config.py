from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    assistant_db_path: Path = Path(__file__).resolve().parent.parent.parent / "data" / "assistant.db"

    # Models (Anthropic) — IDs from https://docs.anthropic.com/en/docs/about-claude/models/overview
    classifier_model: str = "claude-haiku-4-5"
    agent_model: str = "claude-sonnet-4-20250514"
    thinking_budget_tokens: int = 10_000
    max_tokens: int = 16_000

    # Arize Phoenix observability — leave empty to disable tracing
    # Self-hosted: run `python -m phoenix.server.main` and set the endpoint below
    # Cloud: set both endpoint and api_key from https://app.phoenix.arize.com
    phoenix_collector_endpoint: str = ""
    phoenix_api_key: str = ""


settings = Settings()
