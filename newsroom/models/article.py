"""Pydantic models for articles, scored articles, and news digests."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Article(BaseModel):
    """A raw article discovered by the scanner."""

    title: str
    url: str
    source: str = ""
    summary: str = ""
    published_at: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    content: str = ""
    pre_score: float = 0.0

    def fingerprint(self) -> str:
        """Normalized key for deduplication (lowercase title + domain)."""
        from urllib.parse import urlparse

        domain = urlparse(self.url).netloc.lower()
        return f"{self.title.lower().strip()}|{domain}"


class ScannerOutput(BaseModel):
    """Structured output from the scanner agent."""

    articles: list[Article]


class ScoredArticle(BaseModel):
    """An article with editorial scoring and dedup metadata."""

    article: Article
    relevance_score: float = 0.0
    novelty_score: float = 0.0
    overall_score: float = 0.0
    reasoning: str = ""
    is_duplicate: bool = False
    duplicate_of: str | None = None


class ScoredArticles(BaseModel):
    """Structured output from the editor agent."""

    articles: list[ScoredArticle]


class DigestSection(BaseModel):
    """A thematic section within a digest."""

    heading: str
    articles: list[ScoredArticle] = Field(default_factory=list)
    commentary: str = ""


class NewsDigest(BaseModel):
    """A curated news digest ready for publishing."""

    title: str = ""
    date: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d"))
    summary: str = ""
    sections: list[DigestSection] = Field(default_factory=list)
    markdown: str = ""
    article_count: int = 0


class DigestOutput(BaseModel):
    """Structured output from the writer agent — the full digest as markdown."""

    markdown: str
