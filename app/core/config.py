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

    # Evolution API - Free WhatsApp Gateway
    evolution_url: str = "http://localhost:8080"
    evolution_api_key: str = ""
    evolution_instance_name: str = "inika"
    evolution_webhook_url: Optional[str] = None  # Override webhook URL (e.g., https://yourdomain.com). If None, uses api_base_url.

    # API base URL (for building webhook URLs that Evolution can reach)
    api_base_url: str = "http://localhost:8000"

    # Inika External Booking API
    inika_api_key: str = ""
    inika_booking_key: str = ""

    # Weather API (OpenWeatherMap)
    openweather_api_key: str = ""

    # WAHA - Production WhatsApp Gateway (alternative to Evolution API)
    waha_url: str = "http://localhost:3001"
    waha_api_key: str = ""

    # Baileys Gateway - Local multi-tenant WhatsApp gateway (Node.js service)
    baileys_gateway_url: str = "http://localhost:3002"
    baileys_gateway_api_key: str = ""

    # Evolution webhook → tenant when multiple tenants exist (UUID). Empty = first tenant (single-hotel setups).
    webhook_whatsapp_tenant_id: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()