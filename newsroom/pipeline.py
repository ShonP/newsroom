"""Pipeline: orchestrates scan → dedup → score → extract → curate → format → output."""

from __future__ import annotations

import asyncio
from pathlib import Path

from newsroom.agents.editor import score_and_curate
from newsroom.agents.scanner import scan_sources
from newsroom.agents.writer import write_digest
from newsroom.dedup import DedupDB, dedup_articles
from newsroom.editorial import load_editorial_profile
from newsroom.log import log, new_run_id
from newsroom.middleware import get_token_usage, reset_token_usage
from newsroom.models.article import Article
from newsroom.scoring import filter_articles
from newsroom.tools.extract import extract_article_text


async def _enrich_articles(articles: list[Article], max_extract: int = 10) -> list[Article]:
    """Extract full article text for top-scored articles concurrently."""
    to_extract = articles[:max_extract]
    if not to_extract:
        return articles

    async def _extract_one(article: Article) -> None:
        text = await asyncio.to_thread(extract_article_text, article.url)
        if text:
            article.content = text

    tasks = [_extract_one(a) for a in to_extract]
    await asyncio.gather(*tasks, return_exceptions=True)

    enriched = sum(1 for a in to_extract if a.content)
    log.info("Extraction: enriched %d/%d articles with full text", enriched, len(to_extract))
    return articles


async def run_pipeline(output_path: str = "digest.md", top_n: int = 15) -> str:
    """Execute the full newsroom pipeline.

    Steps:
        1. Scan all sources for articles
        2. Cross-run dedup (URL normalization + fuzzy title matching)
        3. Deterministic quality scoring + filtering
        4. Full text extraction for top candidates
        5. LLM editor: final scoring, dedup, curation with editorial profile
        6. Write formatted digest
        7. Mark curated articles as seen for future dedup

    Returns the generated digest markdown.
    """
    run_id = new_run_id()
    reset_token_usage()
    log.info("Pipeline starting [%s]", run_id)

    # Step 1: Scan
    log.info("Step 1/6: Scanning sources")
    articles = await scan_sources()
    raw_count = len(articles)
    if not articles:
        log.warning("No articles discovered — producing empty digest")

    # Step 2: Cross-run dedup
    log.info("Step 2/6: Deduplicating %d articles", len(articles))
    dedup_db = DedupDB()
    try:
        articles = dedup_articles(articles, dedup_db)
        deduped_count = len(articles)

        # Step 3: Deterministic scoring
        log.info("Step 3/6: Scoring %d articles", len(articles))
        articles = filter_articles(articles, threshold=5.0)
        scored_count = len(articles)

        # Step 4: Extract full text for top candidates
        log.info("Step 4/6: Extracting full text for top %d articles", min(top_n, len(articles)))
        articles = await _enrich_articles(articles, max_extract=top_n)
        enriched_count = sum(1 for a in articles if a.content)

        # Step 5: LLM editor curation with editorial profile
        log.info("Step 5/6: Editor curating %d articles", len(articles))
        editorial_profile = load_editorial_profile()
        curated = await score_and_curate(articles, top_n=top_n, editorial_profile=editorial_profile)
        curated_count = len(curated)

        # Step 6: Write digest
        log.info("Step 6/6: Writing digest from %d curated articles", len(curated))
        digest_md = await write_digest(curated)

        # Mark curated articles as seen for future cross-run dedup
        curated_articles = [sa.article for sa in curated]
        dedup_db.mark_seen_batch(curated_articles)
        dedup_db.cleanup()
    finally:
        dedup_db.close()

    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(digest_md, encoding="utf-8")

    usage = get_token_usage()
    log.info(
        "Pipeline complete [%s]: %d raw → %d deduped → %d scored → %d enriched → %d curated, %d tokens",
        run_id,
        raw_count,
        deduped_count,
        scored_count,
        enriched_count,
        curated_count,
        usage.total_tokens,
    )
    log.info("Digest saved to %s", out)

    return digest_md


def run_pipeline_sync(output_path: str = "digest.md", top_n: int = 15) -> str:
    """Synchronous wrapper for run_pipeline."""
    return asyncio.run(run_pipeline(output_path=output_path, top_n=top_n))


async def run_scan_only() -> list[dict]:  # type: ignore[type-arg]
    """Run only the scan step, returning raw article dicts."""
    new_run_id()
    log.info("Scan-only mode")
    articles = await scan_sources()
    return [a.model_dump() for a in articles]
