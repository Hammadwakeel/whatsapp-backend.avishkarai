from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/inika_db"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # App
    app_env: str = "development"
    debug: bool = True
    cors_origins: List[str] = ["http://localhost:3000"]

    # Wiki / LLM (SHARED across all tenants)
    wiki_path: str = "wiki"
    openrouter_api_key: str = ""
    llm_model: str = "anthropic/claude-3-haiku"

    # Web Search (SHARED across all tenants)
    tavily_api_key: str = ""

    # Baileys Gateway - Local multi-tenant WhatsApp gateway (Node.js service)
    baileys_gateway_url: str = "http://localhost:3002"
    baileys_gateway_api_key: str = ""

    # API base URL (for building webhook URLs)
    api_base_url: str = "http://localhost:8000"

    # Inika External Booking API
    inika_api_key: str = ""
    inika_booking_key: str = ""

    # Weather API (OpenWeatherMap)
    openweather_api_key: str = ""

    # Webhook tenant routing when multiple tenants share one backend (UUID). Empty = first tenant.
    webhook_whatsapp_tenant_id: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()