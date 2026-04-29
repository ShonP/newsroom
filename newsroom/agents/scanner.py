"""Scanner agent: discovers AI/tech news from multiple sources."""

from __future__ import annotations

import json

from agent_framework._agents import Agent

from newsroom.client import get_chat_client
from newsroom.config import get_settings
from newsroom.log import log
from newsroom.middleware import caching, llm_call_logging, retry, tool_call_logging
from newsroom.models.article import Article
from newsroom.tools.github_trending import github_trending
from newsroom.tools.hackernews import fetch_hackernews
from newsroom.tools.reddit import fetch_reddit
from newsroom.tools.rss import fetch_rss
from newsroom.tools.web_search import web_search

SUBREDDITS = ["MachineLearning", "artificial", "LocalLLaMA"]

SEARCH_QUERIES = [
    "AI news today",
    "machine learning breakthrough",
    "new open source AI model",
    "tech industry news today",
]


def _build_scanner_prompt() -> str:
    """Build scanner prompt with configurable RSS feeds."""
    settings = get_settings()
    feeds_list = "\n".join(f"- {f}" for f in settings.rss_feeds)

    return f"""\
You are a news scanner specializing in AI, machine learning, and technology news.

Your job is to discover the latest important news stories using the tools available.

Strategy:
1. Use web_search to find breaking AI/ML/tech news
2. Use fetch_rss to pull from key tech news feeds
3. Use github_trending to find notable new open-source projects
4. Use fetch_reddit to check AI/ML communities for discussions
5. Use fetch_hackernews to get top stories from Hacker News

Key RSS feeds to check:
{feeds_list}

Key subreddits:
- MachineLearning
- artificial
- LocalLLaMA

Search queries to try:
- "AI news today"
- "machine learning breakthrough"
- "new open source AI model"
- "tech industry news today"

After gathering results, compile ALL discovered articles into a JSON array.
Each article must have: title, url, source, summary, published_at (if available), tags.

Your final message MUST be a valid JSON array of article objects. Nothing else.
"""


async def scan_sources() -> list[Article]:
    """Run the scanner agent to discover articles from all sources."""
    agent = Agent(
        client=get_chat_client(),
        name="news-scanner",
        instructions=_build_scanner_prompt(),
        tools=[web_search, fetch_rss, github_trending, fetch_reddit, fetch_hackernews],
        middleware=[tool_call_logging, caching, retry, llm_call_logging],
    )

    prompt = (
        "Scan all available sources for the latest AI, ML, and technology news. "
        "Use ALL tools: web_search, fetch_rss, github_trending, fetch_reddit, and fetch_hackernews. "
        "Return a JSON array of article objects."
    )

    log.info("Starting news scan across all sources")
    response = await agent.run(prompt)

    return _parse_articles(response.text)


def _parse_articles(text: str) -> list[Article]:
    """Parse the scanner's JSON output into Article objects."""
    # Try to extract JSON from the response
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("articles", [])
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                log.error("Failed to parse scanner output as JSON")
                return []
        else:
            log.error("No JSON array found in scanner output")
            return []

    articles: list[Article] = []
    for item in data:
        if isinstance(item, dict) and item.get("title") and item.get("url"):
            try:
                articles.append(Article.model_validate(item))
            except Exception:
                articles.append(
                    Article(
                        title=str(item.get("title", "")),
                        url=str(item.get("url", "")),
                        source=str(item.get("source", "")),
                        summary=str(item.get("summary", ""))[:500],
                    )
                )

    log.info("Scanner discovered %d articles", len(articles))
    return articles
