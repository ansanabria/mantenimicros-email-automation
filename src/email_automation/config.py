from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "email-automation"
    app_env: str = "development"
    # Public-facing base URL (e.g. the ngrok tunnel URL).
    # All other derived URLs default to this value when not set explicitly.
    base_url: str = "http://localhost:8000"

    database_url: str = "sqlite+aiosqlite:///./data/email_automation.db"
    attachment_storage_path: Path = Path("data/attachments")
    polling_interval_seconds: int = 60
    supplier_offer_ttl_days: int = 30
    match_threshold: float = 65.0

    company_name: str = "Computer Sales"
    sales_signature: str = "Equipo Comercial"
    default_reply_language: str = "es"

    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemini-2.5-flash-lite"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str | None = None
    openrouter_app_name: str = "email-automation"

    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_auth_mode: Literal["application", "delegated"] = "application"
    microsoft_mailbox: str | None = None
    microsoft_graph_base_url: str = "https://graph.microsoft.com/v1.0"
    microsoft_token_cache_path: Path = Path("data/msal_token_cache.json")

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_webhook_secret: str = Field(default="change-me")
    # If not set explicitly, defaults to base_url (the ngrok tunnel URL).
    # This means you only need to update BASE_URL in .env when ngrok restarts.
    telegram_webhook_url: str | None = None

    @model_validator(mode="after")
    def _derive_telegram_webhook_url(self) -> "Settings":
        if not self.telegram_webhook_url:
            self.telegram_webhook_url = self.base_url
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.attachment_storage_path.mkdir(parents=True, exist_ok=True)
    settings.microsoft_token_cache_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
