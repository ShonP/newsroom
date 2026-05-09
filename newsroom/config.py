"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration loaded from .env file and environment variables."""

    azure_api_key: str = ""
    openai_base_url: str = ""
    model: str = "gpt-5.5"
    tavily_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    rss_feeds: list[str] = [
        "https://techcrunch.com/feed/",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.theverge.com/rss/index.xml",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings instance (created on first call)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
