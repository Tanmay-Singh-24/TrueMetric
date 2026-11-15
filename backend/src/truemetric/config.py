"""Every setting the app reads, taken from environment variables in one place."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    owner_database_url: str
    readonly_password: str
    groq_api_key: str
    groq_model: str
    cors_origins: list[str]
    rate_limit_per_minute: int
    rate_limit_per_day: int


def load_settings() -> Settings:
    """Build the Settings object from the current environment."""
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    return Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        owner_database_url=os.environ.get("OWNER_DATABASE_URL", ""),
        readonly_password=os.environ.get("READONLY_PASSWORD", ""),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        groq_model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        cors_origins=[origin.strip() for origin in cors_origins.split(",") if origin.strip()],
        rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10")),
        rate_limit_per_day=int(os.environ.get("RATE_LIMIT_PER_DAY", "300")),
    )


settings = load_settings()
