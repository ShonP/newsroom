"""Pipeline: orchestrates scan → dedup → score → extract → curate → format → output.

Uses the Agent Framework Functional Workflow API with @workflow/@step decorators
and FileCheckpointStorage for resumable execution.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent_framework import FileCheckpointStorage, RunContext, step, workflow
from shon_toolkit.log import attach_file_handler, detach_file_handler, log, new_run_id
from shon_toolkit.middleware import get_token_usage, reset_token_usage

from newsroom.agents.editor import score_and_curate
from newsroom.agents.scanner import scan_sources
from newsroom.agents.writer import write_digest
from newsroom.dedup import DedupDB, dedup_articles
from newsroom.editorial import load_editorial_profile
from newsroom.models.article import Article, ScoredArticle
from newsroom.scoring import filter_articles
from newsroom.tools.extract import extract_article_text

_CHECKPOINT_DIR = Path("checkpoints")


def _get_checkpoint_storage() -> FileCheckpointStorage:
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return FileCheckpointStorage(str(_CHECKPOINT_DIR))


@step
async def step_scan() -> list[Article]:
    log.info("Step 1/6: Scanning sources")
    return await scan_sources()


@step
async def step_dedup(articles: list[Article]) -> list[Article]:
    log.info("Step 2/6: Deduplicating %d articles", len(articles))
    dedup_db = DedupDB()
    try:
        return dedup_articles(articles, dedup_db)
    finally:
        dedup_db.close()


@step
async def step_score(articles: list[Article]) -> list[Article]:
    log.info("Step 3/6: Scoring %d articles", len(articles))
    return filter_articles(articles, threshold=5.0)


@step
async def step_extract(articles: list[Article], top_n: int) -> list[Article]:
    log.info("Step 4/6: Extracting full text for top %d articles", min(top_n, len(articles)))
    to_extract = articles[:top_n]

    async def _extract_one(article: Article) -> None:
        text = await asyncio.to_thread(extract_article_text, article.url)
        if text:
            article.content = text

    await asyncio.gather(*[_extract_one(a) for a in to_extract], return_exceptions=True)

    enriched = sum(1 for a in to_extract if a.content)
    log.info("Extraction: enriched %d/%d articles with full text", enriched, len(to_extract))
    return articles


@step
async def step_curate(articles: list[Article], top_n: int) -> list[ScoredArticle]:
    log.info("Step 5/6: Editor curating %d articles", len(articles))
    editorial_profile = load_editorial_profile()
    return await score_and_curate(articles, top_n=top_n, editorial_profile=editorial_profile)


@step
async def step_write(curated: list[ScoredArticle]) -> str:
    log.info("Step 6/6: Writing digest from %d curated articles", len(curated))
    return await write_digest(curated)


@workflow(name="newsroom_pipeline")
async def newsroom_workflow(input_data: Any, ctx: RunContext) -> str:
    top_n = 15
    if isinstance(input_data, dict):
        top_n = input_data.get("top_n", 15)

    articles = await step_scan()
    if not articles:
        log.warning("No articles discovered — producing empty digest")
        return await step_write([])

    articles = await step_dedup(articles)
    articles = await step_score(articles)
    articles = await step_extract(articles, top_n)
    curated = await step_curate(articles, top_n)
    digest_md = await step_write(curated)

    ctx.set_state("curated_urls", [sa.article.url for sa in curated])
    return digest_md


async def run_pipeline(
    output_path: str = "digest.md",
    top_n: int = 15,
    checkpoint_id: str | None = None,
) -> str:
    run_id = new_run_id()
    reset_token_usage()
    attach_file_handler()
    log.info("Pipeline starting [%s]", run_id)

    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    storage = _get_checkpoint_storage()

    if checkpoint_id:
        log.info("Resuming from checkpoint: %s", checkpoint_id)
        result = await newsroom_workflow.run(
            checkpoint_id=checkpoint_id,
            checkpoint_storage=storage,
        )
    else:
        result = await newsroom_workflow.run(
            {"top_n": top_n},
            checkpoint_storage=storage,
        )

    outputs = result.get_outputs()
    digest_md = str(outputs[0]) if outputs else ""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(digest_md, encoding="utf-8")

    usage = get_token_usage()
    log.info("Pipeline complete [%s], %d tokens, saved to %s", run_id, usage.total_tokens, out)
    detach_file_handler()

    return digest_md


def run_pipeline_sync(output_path: str = "digest.md", top_n: int = 15) -> str:
    return asyncio.run(run_pipeline(output_path=output_path, top_n=top_n))


async def run_scan_only() -> list[dict]:  # type: ignore[type-arg]
    new_run_id()
    log.info("Scan-only mode")
    articles = await scan_sources()
    return [a.model_dump() for a in articles]
