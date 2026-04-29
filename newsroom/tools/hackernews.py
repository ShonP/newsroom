"""Hacker News top stories fetcher tool."""

from __future__ import annotations

import json

import httpx
from agent_framework._tools import tool

from newsroom.log import log

_HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
_HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
_TIMEOUT = 15


def _fetch_item(client: httpx.Client, item_id: int) -> dict[str, str | int] | None:
    """Fetch a single HN item by ID."""
    try:
        resp = client.get(_HN_ITEM.format(id=item_id), timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data or data.get("type") != "story":
            return None
        return {
            "title": data.get("title", ""),
            "url": data.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
            "score": data.get("score", 0),
            "author": data.get("by", ""),
            "num_comments": data.get("descendants", 0),
            "hn_id": item_id,
            "time": data.get("time", 0),
        }
    except Exception:
        return None


@tool
def fetch_hackernews(max_items: int = 10) -> str:
    """Fetch top stories from Hacker News.

    Args:
        max_items: Maximum number of stories to return (default 10).
    """
    try:
        with httpx.Client() as client:
            resp = client.get(_HN_TOP, timeout=_TIMEOUT)
            resp.raise_for_status()
            top_ids: list[int] = resp.json()[: max_items * 2]  # fetch extra for filtering

            stories: list[dict[str, str | int]] = []
            for item_id in top_ids:
                if len(stories) >= max_items:
                    break
                item = _fetch_item(client, item_id)
                if item and item.get("title"):
                    stories.append(item)

        log.debug("HN: fetched %d stories", len(stories))
        return json.dumps({"stories": stories})
    except Exception as e:
        log.warning("HN fetch failed: %s", e)
        return json.dumps({"stories": [], "error": str(e)})
