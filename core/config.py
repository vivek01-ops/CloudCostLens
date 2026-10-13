"""Application configuration.

All settings are sourced from the environment (optionally a local ``.env`` file for
development only). Real secrets must never be committed; see ``.env.example`` for the
expected variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_REGIONS: tuple[str, ...] = (
    "us-east-1",
    "us-west-2",
    "eu-west-1",
    "ap-south-1",
)


class Settings(BaseSettings):
    """Runtime configuration for CloudCostLens."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Application -------------------------------------------------------
    app_name: str = "CloudCostLens"
    version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = False

    # When true the UI clearly labels all data as demonstration fixtures.
    demo_mode: bool = True

    # -- Database ----------------------------------------------------------
    # Example: postgresql+psycopg://ccl:ccl@localhost:5432/cloudcostlens
    database_url: str = "postgresql+psycopg://ccl:ccl@localhost:5432/cloudcostlens"

    # -- Security ----------------------------------------------------------
    # Signs session JWTs. MUST be overridden in production.
    secret_key: str = Field(default="dev-insecure-change-me")
    access_token_ttl_seconds: int = 60 * 30
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt AWS external IDs at rest.
    fernet_key: str | None = None
    session_cookie_name: str = "ccl_session"
    cookie_secure: bool = True
    cookie_domain: str | None = None

    # -- CORS / frontend ---------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    api_base_path: str = "/api/v1"

    # -- AWS ---------------------------------------------------------------
    aws_default_region: str = "us-east-1"
    aws_price_list_region: str = "us-east-1"
    default_regions: list[str] = Field(default_factory=lambda: list(DEFAULT_REGIONS))
    aws_connect_timeout_seconds: int = 10
    aws_read_timeout_seconds: int = 30
    aws_max_attempts: int = 5

    # -- Engine thresholds (defaults; overridable per-org via rule_configs) -
    idle_cpu_avg_threshold_pct: float = 5.0
    idle_cpu_p95_threshold_pct: float = 15.0
    idle_observation_days: int = 14
    min_observation_days: int = 7

    @field_validator("cors_origins", "default_regions", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow comma-separated env values for list fields."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    def validate_for_runtime(self) -> None:
        """Fail fast on unsafe production configuration."""
        if self.is_production:
            if self.secret_key == "dev-insecure-change-me":
                raise RuntimeError("SECRET_KEY must be set in production")
            if not self.fernet_key:
                raise RuntimeError("FERNET_KEY must be set in production")
            if not self.is_production or not self.cookie_secure:
                raise RuntimeError("COOKIE_SECURE must be enabled in production")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
