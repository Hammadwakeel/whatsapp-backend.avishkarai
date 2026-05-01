from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()