"""Application settings, loaded from environment variables and validated at startup."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRETS = {"", "replace-me", "change-me", "changeme", "secret"}
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NEXUS"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"
    app_secret_key: str = "replace-me"  # noqa: S105 - placeholder; rejected in production

    database_url: str = "sqlite:///./nexus_dev.sqlite3"
    redis_url: str = "redis://localhost:6379/0"

    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    github_api_base: str = "https://api.github.com"

    ai_provider: Literal["none", "ollama", "openai_compatible"] = "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""

    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid LOG_LEVEL: {value}")
        return level

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _enforce_production_rules(self) -> "Settings":
        if self.app_env != "production":
            return self
        if (
            self.app_secret_key.lower() in PLACEHOLDER_SECRETS
            or len(self.app_secret_key) < MIN_PRODUCTION_SECRET_LENGTH
        ):
            raise ValueError(
                "APP_SECRET_KEY must be a unique random value of at least "
                f"{MIN_PRODUCTION_SECRET_LENGTH} characters in production"
            )
        if "*" in self.cors_origin_list:
            raise ValueError("CORS wildcard origin is not allowed in production")
        if self.database_url.startswith("sqlite"):
            raise ValueError("SQLite is not allowed in production; use PostgreSQL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
