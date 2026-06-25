"""Application settings, sourced from environment / .env (staging vs production split)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"  # local | staging | production

    database_url: str = "postgresql://bot:bot@localhost:5432/clinicbot"
    redis_url: str = "redis://localhost:6379/0"

    # Which LLM backend the booking loop uses: "gemini" | "claude".
    llm_provider: str = "gemini"

    anthropic_api_key: str = ""
    classifier_model: str = "claude-haiku-4-5"
    escalation_model: str = "claude-sonnet-4-6"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"

    encryption_key: str = ""
    whatsapp_verify_token: str = "dev-verify-token"

    # Single shared key protecting the admin API + web UI (Phase 2; RBAC is later).
    admin_api_key: str = "change-me-admin"

    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy needs the asyncpg driver; Railway/Heroku hand out plain `postgresql://`."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
