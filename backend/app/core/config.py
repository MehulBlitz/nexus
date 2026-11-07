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
    app_version: str = "0.2.0"
    app_env: Literal["development", "test", "production"] = "development"
    app_secret_key: str = "replace-me"  # noqa: S105 - placeholder; rejected in production

    database_url: str = "sqlite:///./nexus_dev.sqlite3"
    redis_url: str = "redis://localhost:6379/0"

    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    # --- Sessions -------------------------------------------------------------
    session_cookie_name: str = "nexus_session"
    csrf_cookie_name: str = "nexus_csrf"
    session_ttl_hours: int = 24 * 7
    cookie_secure: bool | None = None  # default: secure in production only

    # --- Rate limits (per client IP, single process) ---------------------------
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 240
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10

    # --- GitHub ---------------------------------------------------------------
    github_api_base: str = "https://api.github.com"
    github_raw_base: str = "https://raw.githubusercontent.com"
    # Optional unauthenticated-or-PAT access. Never required for public repositories.
    github_token: str = ""
    github_timeout_seconds: float = 20.0
    github_max_retries: int = 2

    # --- Ingestion limits ------------------------------------------------------
    max_index_files: int = 400
    max_file_bytes: int = 256 * 1024
    max_total_bytes: int = 20 * 1024 * 1024
    max_symbols_per_file: int = 400
    index_fetch_concurrency: int = 4

    # --- Jobs ------------------------------------------------------------------
    # "inline" runs jobs in a background thread of the API process (development).
    # "worker" only enqueues; `python -m app.workers.runner` executes them.
    job_execution_mode: Literal["inline", "worker"] = "inline"
    job_poll_seconds: float = 1.0
    job_max_attempts: int = 2

    # --- AI (optional) ----------------------------------------------------------
    ai_provider: Literal["none", "ollama", "openai_compatible"] = "none"
    ai_base_url: str = "http://localhost:11434"
    ai_model: str = ""
    ai_api_key: str = ""
    ai_timeout_seconds: float = 45.0

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

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env == "production"

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
