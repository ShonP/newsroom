"""Deterministic quality scoring for articles — runs before the LLM editor."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from shon_toolkit.log import log

from newsroom.models.article import Article

# Source tier scores (0-10 scale). Higher = more trusted.
SOURCE_TIERS: dict[str, float] = {
    "techcrunch.com": 9.0,
    "arstechnica.com": 8.5,
    "theverge.com": 8.0,
    "wired.com": 8.0,
    "thenewstack.io": 7.5,
    "venturebeat.com": 7.5,
    "infoworld.com": 7.0,
    "openai.com": 8.0,
    "blog.google": 8.0,
    "ai.meta.com": 8.0,
    "anthropic.com": 8.0,
    "huggingface.co": 7.5,
    "arxiv.org": 8.5,
    "github.com": 7.0,
    "news.ycombinator.com": 7.0,
    "reddit.com": 6.0,
    "medium.com": 5.0,
    "dev.to": 5.5,
    "substack.com": 6.0,
}

_DEFAULT_SOURCE_SCORE = 5.0

# Clickbait patterns
_CLICKBAIT_RE = re.compile(
    r"(?i)(you won.t believe|shocking|mind.?blow|this is huge|game.?chang|"
    r"insane|unbelievable|jaw.?drop|secret|hack\b)",
)


def _get_source_score(url: str) -> float:
    """Score based on source tier (0-10)."""
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    for pattern, score in SOURCE_TIERS.items():
        if pattern in domain:
            return score
    return _DEFAULT_SOURCE_SCORE


def _recency_score(published_at: str) -> float:
    """Score based on how recent the article is (0-10). 10 = <1h, 0 = >48h."""
    if not published_at:
        return 5.0  # unknown → neutral

    try:
        # Try common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(published_at.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                break
            except ValueError:
                continue
        else:
            return 5.0

        age_hours = (datetime.now(UTC) - dt).total_seconds() / 3600
        if age_hours < 1:
            return 10.0
        if age_hours < 6:
            return 8.5
        if age_hours < 12:
            return 7.0
        if age_hours < 24:
            return 5.5
        if age_hours < 48:
            return 3.0
        return 1.0
    except Exception:
        return 5.0


def _title_quality_score(title: str) -> float:
    """Score title quality (0-10). Penalizes bad patterns."""
    if not title:
        return 0.0

    score = 7.0
    length = len(title)

    # Penalize too short or too long
    if length < 15:
        score -= 3.0
    elif length < 30:
        score -= 1.0
    elif length > 150:
        score -= 2.0

    # Penalize ALL CAPS
    if title == title.upper() and len(title) > 10:
        score -= 3.0

    # Penalize clickbait
    if _CLICKBAIT_RE.search(title):
        score -= 2.5

    # Bonus for having a colon/dash (usually more descriptive)
    if ":" in title or " — " in title or " - " in title:
        score += 0.5

    return max(0.0, min(10.0, score))


def _author_score(author: str) -> float:
    """Bonus for having an author (0-2)."""
    return 1.5 if author.strip() else 0.0


def score_article(article: Article) -> float:
    """Compute a deterministic quality score (0-10) for an article."""
    source = _get_source_score(article.url) * 0.35
    recency = _recency_score(article.published_at) * 0.25
    title_q = _title_quality_score(article.title) * 0.25
    author_bonus = _author_score(article.author)

    # Weighted combination (weights sum to ~1.0)
    raw = source + recency + title_q + author_bonus
    # Normalize to 0-10 (max possible ≈ 3.5+2.5+2.5+1.5=10)
    return round(min(10.0, max(0.0, raw)), 2)


def filter_articles(
    articles: list[Article],
    threshold: float = 5.0,
) -> list[Article]:
    """Score and filter articles, returning those above threshold sorted by score."""
    scored: list[tuple[float, Article]] = []
    for article in articles:
        s = score_article(article)
        article.pre_score = s
        scored.append((s, article))

    scored.sort(key=lambda x: x[0], reverse=True)

    above = [(s, a) for s, a in scored if s >= threshold]
    below_count = len(scored) - len(above)

    log.info(
        "Scoring: %d articles scored, %d above %.1f threshold, %d filtered out",
        len(scored),
        len(above),
        threshold,
        below_count,
    )

    return [a for _, a in above]
