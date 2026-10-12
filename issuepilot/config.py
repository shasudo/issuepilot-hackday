from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration, loaded from `.env` on first use.

    Model IDs are deliberately unset by default: the caller picks the
    provider via LLM_PROVIDER and must set that provider's model ID
    explicitly (for the Hack Day: the organizer-confirmed ID).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    github_token: str
    github_api_base: str = "https://api.github.com"

    llm_provider: Literal["anthropic", "openai", "google"] = "google"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    anthropic_model: str | None = None
    openai_model: str | None = None
    google_model: str | None = None

    cache_db_path: Path = Path(".issuepilot/cache.db")
    trace_db_path: Path = Path(".issuepilot/traces.db")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Process-wide cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
