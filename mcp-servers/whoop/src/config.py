"""Configuration for the WHOOP MCP server."""

from __future__ import annotations

from functools import lru_cache

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    whoop_api_base_url: str = Field(
        default="https://api.prod.whoop.com/developer/v2",
        validation_alias="WHOOP_API_BASE_URL",
    )
    whoop_auth_base_url: str = Field(
        default="https://api.prod.whoop.com/oauth/oauth2",
        validation_alias="WHOOP_AUTH_BASE_URL",
    )
    whoop_local_timezone: str = Field(
        default="America/Los_Angeles",
        validation_alias="WHOOP_LOCAL_TIMEZONE",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()


settings = get_settings()
