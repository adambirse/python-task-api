"""Application settings, read from environment variables (or a .env file).

pydantic-settings validates types at startup, so a missing or malformed
setting fails fast instead of causing a confusing error mid-request.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Task API"
    database_url: str = "sqlite:///./task_api.db"

    jwt_secret_key: str = Field(default="dev-only-insecure-secret-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Optional: create an admin account at startup. Never set these in production.
    seed_admin_username: str | None = None
    seed_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is only parsed once. Override in tests if needed."""
    return Settings()
