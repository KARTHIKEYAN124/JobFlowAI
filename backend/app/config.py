import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Vercel functions can only write to /tmp. This keeps an unconfigured demo
    # healthy; production deployments should always provide DATABASE_URL.
    database_url: str = (
        "sqlite+aiosqlite:////tmp/jobflow.db" if os.getenv("VERCEL") else "sqlite+aiosqlite:///./jobflow.db"
    )
    jwt_secret: str = Field("development-only-change-me-now", min_length=24)
    webhook_secret: str = Field("development-webhook-secret", min_length=16)
    cors_origins: str = "http://localhost:3000"
    access_token_minutes: int = 60
    max_resume_bytes: int = 5_000_000
    ai_provider: str = "disabled"
    ai_base_url: str = "http://ollama:11434"
    ai_api_key: str = ""
    ai_chat_model: str = "llama3.2:3b"
    ai_embedding_model: str = "nomic-embed-text"
    ai_input_cost_per_million: float = 0.0
    ai_output_cost_per_million: float = 0.0
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "jobflow"
    n8n_url: str = "http://n8n:5678"
    n8n_api_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def async_postgres_url(cls, value: str) -> str:
        if not value.startswith(("postgres://", "postgresql://")):
            return value
        value = value.replace("postgres://", "postgresql://", 1)
        parts = urlsplit(value)
        query = [
            ("ssl" if key == "sslmode" else key, item)
            for key, item in parse_qsl(parts.query)
            if key != "channel_binding"
        ]
        return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment))


settings = Settings()
