"""Reddit subreddit fetcher tool using OAuth2."""

from __future__ import annotations

import json

import httpx
from agent_framework._tools import tool
from shon_toolkit.log import log

from newsroom.config import get_settings

USER_AGENT = "openclaw-newsroom:v0.1 (by /u/openclaw_bot)"


def _get_reddit_token(client_id: str, client_secret: str) -> str | None:
    """Obtain a Reddit OAuth2 app-only access token."""
    try:
        resp = httpx.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        log.warning("Reddit auth failed: %s", e)
        return None


@tool
def fetch_reddit(subreddit: str, max_posts: int = 10) -> str:
    """Fetch top posts from a Reddit subreddit.

    Args:
        subreddit: Subreddit name without the r/ prefix (e.g. 'MachineLearning').
        max_posts: Maximum number of posts to return.
    """
    settings = get_settings()

    # Try OAuth2 if credentials are available
    if settings.reddit_client_id and settings.reddit_client_secret:
        token = _get_reddit_token(settings.reddit_client_id, settings.reddit_client_secret)
        if token:
            return _fetch_oauth(subreddit, max_posts, token)

    # Fallback: public JSON endpoint
    return _fetch_public(subreddit, max_posts)


def _fetch_oauth(subreddit: str, max_posts: int, token: str) -> str:
    """Fetch via Reddit OAuth2 API."""
    try:
        resp = httpx.get(
            f"https://oauth.reddit.com/r/{subreddit}/hot",
            params={"limit": max_posts},
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        return _parse_reddit_response(resp.json(), "oauth")
    except Exception as e:
        log.warning("Reddit OAuth fetch failed: %s", e)
        return _fetch_public(subreddit, max_posts)


def _fetch_public(subreddit: str, max_posts: int) -> str:
    """Fetch via Reddit public JSON endpoint (no auth)."""
    try:
        resp = httpx.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": max_posts},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        return _parse_reddit_response(resp.json(), "public")
    except Exception as e:
        log.warning("Reddit public fetch failed for r/%s: %s", subreddit, e)
        return json.dumps({"posts": [], "error": str(e)})


def _parse_reddit_response(data: dict, source: str) -> str:  # type: ignore[type-arg]
    """Parse Reddit API response into structured posts."""
    posts: list[dict[str, str | int]] = []
    children = data.get("data", {}).get("children", [])
    for child in children:
        d = child.get("data", {})
        if d.get("stickied"):
            continue
        posts.append(
            {
                "title": d.get("title", ""),
                "url": d.get("url", ""),
                "permalink": f"https://reddit.com{d.get('permalink', '')}",
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "subreddit": d.get("subreddit", ""),
                "author": d.get("author", ""),
            }
        )

    log.debug(
        "Reddit r/%s: %d posts via %s",
        data.get("data", {}).get("children", [{}])[0].get("data", {}).get("subreddit", "?") if children else "?",
        len(posts),
        source,
    )
    return json.dumps({"posts": posts})
