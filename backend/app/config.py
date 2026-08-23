from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./jobflow.db"
    jwt_secret: str = Field("development-only-change-me-now", min_length=24)
    webhook_secret: str = Field("development-webhook-secret", min_length=16)
    cors_origins: str = "http://localhost:3000"
    access_token_minutes: int = 60
    max_resume_bytes: int = 5_000_000

    @field_validator("database_url", mode="before")
    @classmethod
    def async_postgres_url(cls, value: str) -> str:
        if not value.startswith(("postgres://", "postgresql://")):
            return value
        value = value.replace("postgres://", "postgresql://", 1)
        parts = urlsplit(value)
        query = [("ssl" if key == "sslmode" else key, item) for key, item in parse_qsl(parts.query) if key != "channel_binding"]
        return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment))


settings = Settings()
