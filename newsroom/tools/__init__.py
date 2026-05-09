from __future__ import annotations

import agent_framework._clients as _  # noqa: F401 — resolve circular import
from shon_toolkit.tools.web_search import web_search

from newsroom.tools.extract import extract_article
from newsroom.tools.github_trending import github_trending
from newsroom.tools.hackernews import fetch_hackernews
from newsroom.tools.reddit import fetch_reddit
from newsroom.tools.rss import fetch_rss

__all__ = [
    "extract_article",
    "fetch_hackernews",
    "fetch_reddit",
    "fetch_rss",
    "github_trending",
    "web_search",
]
