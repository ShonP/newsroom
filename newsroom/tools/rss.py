"""RSS/Atom feed fetcher tool."""

from __future__ import annotations

import json

import feedparser
import httpx
from agent_framework._tools import tool

from newsroom.log import log


@tool
def fetch_rss(url: str, max_items: int = 10) -> str:
    """Fetch and parse an RSS or Atom feed, returning structured entries."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        log.warning("RSS fetch failed for %s: %s", url, e)
        return json.dumps({"entries": [], "error": str(e)})

    entries: list[dict[str, str]] = []
    for entry in feed.entries[:max_items]:
        entries.append(
            {
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": entry.get("summary", "")[:500],
                "published": entry.get("published", ""),
                "author": entry.get("author", ""),
            }
        )

    log.debug("RSS %s: %d entries", url[:60], len(entries))
    return json.dumps({"entries": entries, "feed_title": feed.feed.get("title", "")})
