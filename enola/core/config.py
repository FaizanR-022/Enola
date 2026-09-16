"""All configuration comes from the environment (or a local .env file).

Nothing in the codebase reads os.environ directly; it goes through `get_settings()`.
Secrets never have defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ENOLA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- database ---
    database_url: str
    test_database_url: str | None = None

    # --- api ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cookie_secure: bool = False
    session_ttl_hours: int = 720

    # --- owner ---
    owner_name: str = "Owner"
    owner_email: str = "owner@example.com"
    owner_password_hash: str = ""
    timezone: str = "Asia/Karachi"

    # --- logging ---
    log_level: str = "INFO"
    log_json: bool = False

    # --- agent ---
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    agent_model: str = "claude-opus-5"
    embedder: Literal["hash", "voyage"] = "hash"
    voyage_api_key: str = Field(default="", validation_alias="VOYAGE_API_KEY")
    embedding_dim: int = 1024

    # --- files ---
    storage_root: Path = Path("./var/files")

    # --- worker / notifications ---
    daily_brief_hour: int = 7
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return [str(v) for v in value]
        return []

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()
