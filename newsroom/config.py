"""Application settings — extends shon-toolkit's BaseToolkitSettings."""

from __future__ import annotations

from pydantic import Field
from shon_toolkit.client import configure_settings_class
from shon_toolkit.client import get_settings as _get_settings
from shon_toolkit.config import BaseToolkitSettings


class Settings(BaseToolkitSettings):
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    rss_feeds: list[str] = Field(
        default_factory=lambda: [
            "https://techcrunch.com/feed/",
            "https://feeds.arstechnica.com/arstechnica/index",
            "https://www.theverge.com/rss/index.xml",
        ]
    )


configure_settings_class(Settings)


def get_settings() -> Settings:
    return _get_settings()  # type: ignore[return-value]
