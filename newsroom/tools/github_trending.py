"""GitHub trending repositories scraper tool."""

from __future__ import annotations

import json
import re

import httpx
from agent_framework._tools import tool
from shon_toolkit.log import log

TRENDING_URL = "https://github.com/trending"


def _parse_trending_html(html: str) -> list[dict[str, str]]:
    """Extract repo info from GitHub trending page HTML."""
    repos: list[dict[str, str]] = []
    # Each repo is in an <article> with class "Box-row"
    for match in re.finditer(
        r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
        html,
        re.DOTALL,
    ):
        block = match.group(1)

        # Repo path: /owner/repo
        repo_match = re.search(r'href="(/[^/]+/[^/"]+)"', block)
        if not repo_match:
            continue
        repo_path = repo_match.group(1).strip()

        # Description
        desc_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.DOTALL)
        description = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip() if desc_match else ""

        # Language
        lang_match = re.search(r'itemprop="programmingLanguage"[^>]*>([^<]+)', block)
        language = lang_match.group(1).strip() if lang_match else ""

        # Stars today
        stars_match = re.search(r"([\d,]+)\s+stars\s+today", block)
        stars_today = stars_match.group(1).replace(",", "") if stars_match else ""

        repos.append(
            {
                "repo": repo_path.lstrip("/"),
                "url": f"https://github.com{repo_path}",
                "description": description[:300],
                "language": language,
                "stars_today": stars_today,
            }
        )

    return repos


@tool
def github_trending(language: str = "", since: str = "daily") -> str:
    """Scrape GitHub trending repositories.

    Args:
        language: Filter by programming language (e.g. 'python', 'rust'). Empty for all.
        since: Time range — 'daily', 'weekly', or 'monthly'.
    """
    params: dict[str, str] = {"since": since}
    url = TRENDING_URL
    if language:
        url = f"{TRENDING_URL}/{language.lower()}"

    try:
        resp = httpx.get(url, params=params, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        repos = _parse_trending_html(resp.text)
        log.debug("GitHub trending: %d repos (%s, %s)", len(repos), language or "all", since)
        return json.dumps({"repos": repos[:25]})
    except Exception as e:
        log.warning("GitHub trending scrape failed: %s", e)
        return json.dumps({"repos": [], "error": str(e)})
