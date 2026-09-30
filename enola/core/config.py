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
    # Mint an owner session automatically for loopback / private-range clients.
    # For a LAN-only install; turn it off the moment Enola is reachable from the internet.
    autologin: bool = False

    # --- owner ---
    owner_name: str = "Owner"
    owner_email: str = "owner@example.com"
    owner_password_hash: str = ""
    timezone: str = "Asia/Karachi"

    # --- logging ---
    log_level: str = "INFO"
    log_json: bool = False

    # --- agent ---
    model_provider: Literal["anthropic", "google"] = "google"
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", validation_alias="GOOGLE_API_KEY")
    # Model roles. Unset means the provider's own default; see enola/agent/models.py.
    default_model: str | None = None
    agent_model: str | None = None
    utility_model: str | None = None
    embedder: Literal["hash", "voyage"] = "hash"
    voyage_api_key: str = Field(default="", validation_alias="VOYAGE_API_KEY")
    embedding_dim: int = 1024

    # --- job discovery ---
    # The keyless remote boards always run. JSearch needs a free RapidAPI key and is the
    # only free route to onsite Karachi listings; without it that source stays dormant.
    jsearch_api_key: str = Field(default="", validation_alias="JSEARCH_API_KEY")
    # Scored against a posting's title, summary and tags. Edit to re-weight discovery.
    job_skills: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["python", "fastapi", "javascript", "typescript", "react", "node", "express", "postgres", "sql", "docker", "rest", "git"]
    )

    # --- email (IMAP read; sending stays SMTP and Held) ---
    # Gmail with a Google app password: no OAuth app, no consent screen, no weekly
    # token expiry. The password falls back to the SMTP one because it is the same
    # account and the same app password.
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = Field(default="", validation_alias="ENOLA_IMAP_PASSWORD")

    # --- files ---
    storage_root: Path = Path("./var/files")

    # --- worker / notifications ---
    daily_brief_hour: int = 7
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @field_validator("owner_password_hash", mode="before")
    @classmethod
    def _unescape_dollars(cls, value: object) -> object:
        # docker compose interpolates `$` in .env, so the hash is stored with `$$`.
        # Nothing else reads it, and a real scrypt hash never contains `$$`.
        return value.replace("$$", "$") if isinstance(value, str) else value

    @field_validator("job_skills", mode="before")
    @classmethod
    def _split_skills(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return value

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

    @property
    def mail_user(self) -> str:
        return self.imap_user or self.smtp_user

    @property
    def mail_password(self) -> str:
        return self.imap_password or self.smtp_password

    @property
    def imap_enabled(self) -> bool:
        return bool(self.imap_host and self.mail_user and self.mail_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
