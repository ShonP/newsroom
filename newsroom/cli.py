"""CLI entry point for the newsroom pipeline."""

from __future__ import annotations

import asyncio
import json

import click


@click.group()
def main() -> None:
    """OpenClaw Newsroom — AI/tech news scanning and curation pipeline."""


@main.command()
@click.option(
    "--output",
    "-o",
    default="digest.md",
    show_default=True,
    help="Output file path for the news digest.",
)
@click.option(
    "--top-n",
    default=15,
    type=int,
    show_default=True,
    help="Maximum number of articles in the digest.",
)
def digest(output: str, top_n: int) -> None:
    """Run the full pipeline: scan → score → curate → write digest."""
    from newsroom.pipeline import run_pipeline

    asyncio.run(run_pipeline(output_path=output, top_n=top_n))


@main.command()
@click.option(
    "--output",
    "-o",
    default=None,
    help="Save scan results to a JSON file.",
)
def scan(output: str | None) -> None:
    """Scan all sources for articles (no scoring or formatting)."""
    from newsroom.pipeline import run_scan_only

    articles = asyncio.run(run_scan_only())
    result = json.dumps(articles, indent=2, ensure_ascii=False)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result)
        click.echo(f"Saved {len(articles)} articles to {output}")
    else:
        click.echo(result)


if __name__ == "__main__":
    main()
