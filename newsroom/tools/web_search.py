"""Web search tool with fallback: Tavily → DuckDuckGo."""

from __future__ import annotations

import json

from agent_framework._tools import tool

from newsroom.config import get_settings
from newsroom.log import log


def _search_tavily(query: str, max_results: int) -> list[dict[str, str]] | None:
    """Search using Tavily API. Returns None if unavailable."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return None
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        resp = client.search(query, max_results=max_results)
        results = resp.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in results
        ]
    except Exception as e:
        log.warning("Tavily search failed: %s", e)
        return None


def _search_ddg(query: str, max_results: int) -> list[dict[str, str]] | None:
    """Search using DuckDuckGo. Returns None on failure."""
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return []
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        log.warning("DuckDuckGo search failed: %s", e)
        return None


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for news. Tries Tavily first, then DuckDuckGo."""
    for name, fn in [("Tavily", _search_tavily), ("DuckDuckGo", _search_ddg)]:
        results = fn(query, max_results)
        if results is not None:
            if results:
                log.debug("Search via %s: %d results", name, len(results))
            return json.dumps({"results": results, "source": name})

    return json.dumps({"results": [], "error": "All search providers failed."})
