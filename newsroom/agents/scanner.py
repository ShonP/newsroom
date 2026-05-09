"""Scanner agent: discovers AI/tech news from multiple sources."""

from __future__ import annotations

from agent_framework._agents import Agent

from newsroom.client import get_chat_client
from newsroom.config import get_settings
from newsroom.log import log
from newsroom.middleware import caching, llm_call_logging, retry, tool_call_logging
from newsroom.models.article import Article, ScannerOutput
from newsroom.tools.github_trending import github_trending
from newsroom.tools.hackernews import fetch_hackernews
from newsroom.tools.reddit import fetch_reddit
from newsroom.tools.rss import fetch_rss
from newsroom.tools.web_search import web_search


def _build_scanner_prompt() -> str:
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

After gathering results, compile ALL discovered articles into the structured output.
Each article must have: title, url, source, summary, published_at (if available), tags.
"""


async def scan_sources() -> list[Article]:
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
        "Return the discovered articles."
    )

    log.info("Starting news scan across all sources")
    response = await agent.run(prompt, options={"response_format": ScannerOutput})

    if response.value:
        articles = response.value.articles
        log.info("Scanner discovered %d articles", len(articles))
        return articles

    log.error("Scanner failed to produce structured output, raw: %s", response.text[:200])
    return []
