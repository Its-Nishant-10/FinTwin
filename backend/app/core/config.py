"""Settings, read once from the environment.

Add a field here rather than calling os.getenv() inside your module, and add the
matching line to .env.example in the same PR.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://fintwin:fintwin@localhost:5432/fintwin"

    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-5"

    market_data_provider: str = "yfinance"
    market_data_api_key: str | None = None

    simulation_seed: int = 42
    simulation_default_paths: int = 10_000

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
