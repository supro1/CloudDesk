from __future__ import annotations

from decimal import Decimal
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        validate_default=True,
    )

    demo_mode: bool = True
    environment: str = "development"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    jwt_secret: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    database_url: str = "sqlite+aiosqlite:///./data/support.db"
    checkpoint_db_path: str = "./data/checkpoints.db"
    redis_url: str | None = None
    use_fake_redis: bool = True
    llm_provider: str = "fake"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "fake"
    embedding_model: str = "fake"
    embedding_dimensions: int = Field(default=384, gt=0)
    vector_store: Literal["memory", "qdrant"] = "memory"
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "clouddesk_knowledge"
    approval_required_for_refunds: bool = True
    max_refund_without_approval: Decimal = Field(default=Decimal("0"), ge=0)
    tool_timeout_seconds: int = Field(default=30, gt=0)
    rate_limit_per_minute: int = Field(default=120, gt=0)
    sample_data_dir: Path = Path("sample_data")
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "clouddesk-support"
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                decoded = value.split(",")
            value = decoded

        if not isinstance(value, (list, tuple)):
            raise ValueError("CORS_ORIGINS must be a list or comma-separated string")

        origins = [origin.strip() for origin in value if isinstance(origin, str)]
        if not all(isinstance(origin, str) for origin in value):
            raise ValueError("CORS_ORIGINS entries must be strings")
        return [origin for origin in origins if origin]

    @property
    def effective_jwt_secret(self) -> str | None:
        secret = self.supabase_jwt_secret or self.jwt_secret
        return secret.get_secret_value() if secret is not None else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
