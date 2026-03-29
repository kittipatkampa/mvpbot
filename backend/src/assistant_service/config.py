from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""
    assistant_db_path: Path = Path(__file__).resolve().parent.parent.parent / "data" / "assistant.db"

    log_level: str = "INFO"

    # Models (OpenRouter) — IDs from https://openrouter.ai/models
    classifier_model: str = "anthropic/claude-haiku-4-5"
    classifier_max_tokens: int = 1_024
    agent_model: str = "anthropic/claude-sonnet-4-5"
    agent_max_tokens: int = 16_000
    agent_reasoning: dict[str, Any] | None = None

    # Langfuse observability — leave empty to disable tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://us.cloud.langfuse.com"


settings = Settings()
