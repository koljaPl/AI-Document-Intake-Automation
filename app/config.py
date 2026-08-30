"""Application configuration loaded from environment variables and .env file."""

from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for AI Document Intake."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    cache_db_path: Path = Field(default=Path("./intake_cache.db"), alias="CACHE_DB_PATH")
    default_output_dir: Path = Field(default=Path("./output"), alias="DEFAULT_OUTPUT_DIR")
    confidence_floor: float = Field(default=0.80, alias="CONFIDENCE_FLOOR")


def get_settings() -> Settings:
    """Load settings instance."""
    return Settings()
