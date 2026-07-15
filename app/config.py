"""
Central configuration, loaded once from environment variables / .env.

Using pydantic-settings rather than raw os.getenv() calls so config is
validated at startup (fail fast if ANTHROPIC_API_KEY is missing) and is
typed/autocompletable everywhere else in the codebase.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str
    llm_model: str = "claude-haiku-4-5-20251001"
    max_tool_iterations: int = 5
    database_path: str = "./jarvis.db"

    # Static API key required on every /chat request (see
    # app/api/dependencies.py). Required, no default -- the app should
    # refuse to start rather than accidentally run unprotected.
    api_key: str

    # Tavily (free tier, no card) -- used by the web_search tool.
    tavily_api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """
    Cached so Settings() is only constructed (and .env parsed) once per
    process. FastAPI dependencies can call get_settings() cheaply.
    """
    return Settings()
