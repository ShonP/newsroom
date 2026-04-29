"""Editor agent: scores, deduplicates, and curates articles."""

from __future__ import annotations

import json

from agent_framework._agents import Agent

from newsroom.client import get_chat_client
from newsroom.editorial import load_editorial_profile
from newsroom.log import log
from newsroom.middleware import llm_call_logging
from newsroom.models.article import Article, ScoredArticle

_EDITOR_PROMPT_TEMPLATE = """\
You are a senior tech news editor. You receive a list of pre-filtered, pre-scored
articles and must perform final curation.

## Editorial Profile
{editorial_profile}

## Your Tasks

1. **Score** each article on two dimensions (0.0-1.0):
   - relevance_score: How relevant is this to AI/ML/tech professionals?
   - novelty_score: How new/novel is this story? (breaking > rehash)

2. **Deduplicate**: Identify articles covering the same story. Keep the best one,
   mark others as duplicates with is_duplicate=true and duplicate_of=<url of best>.

3. **Overall score**: Compute overall_score = 0.6 * relevance + 0.4 * novelty.

4. **Reasoning**: Brief explanation for each score.

Note: Articles have been pre-scored deterministically (pre_score field). Use this as
a signal but apply your own editorial judgment — pre_score is heuristic, not final.
Articles may also include extracted full text in the "content" field for deeper analysis.

Return ONLY a JSON object with key "articles" containing an array of scored articles.
Each scored article must have:
{{
  "article": {{ "title": "...", "url": "...", "source": "...", "summary": "...", "tags": [] }},
  "relevance_score": 0.0-1.0,
  "novelty_score": 0.0-1.0,
  "overall_score": 0.0-1.0,
  "reasoning": "...",
  "is_duplicate": false,
  "duplicate_of": null
}}

Sort by overall_score descending. Be ruthless — only high-quality, novel stories matter.
"""


async def score_and_curate(
    articles: list[Article],
    top_n: int = 15,
    editorial_profile: str | None = None,
) -> list[ScoredArticle]:
    """Score, deduplicate, and curate articles using the editor agent."""
    if not articles:
        return []

    profile = editorial_profile or load_editorial_profile()
    prompt_text = _EDITOR_PROMPT_TEMPLATE.format(editorial_profile=profile)

    agent = Agent(
        client=get_chat_client(),
        name="news-editor",
        instructions=prompt_text,
        middleware=[llm_call_logging],
    )

    articles_json = json.dumps(
        [a.model_dump(exclude_defaults=False) for a in articles],
        indent=2,
    )
    prompt = (
        f"Here are {len(articles)} pre-filtered articles to evaluate:\n\n"
        f"{articles_json}\n\n"
        f"Score, deduplicate, and return the top articles sorted by quality."
    )

    log.info("Editor scoring %d articles", len(articles))
    response = await agent.run(prompt)

    scored = _parse_scored(response.text)

    # Filter out duplicates and take top N
    curated = [s for s in scored if not s.is_duplicate]
    curated.sort(key=lambda s: s.overall_score, reverse=True)
    curated = curated[:top_n]

    log.info("Editor curated %d articles (from %d candidates)", len(curated), len(articles))
    return curated


def _parse_scored(text: str) -> list[ScoredArticle]:
    """Parse editor's JSON output into ScoredArticle objects."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                log.error("Failed to parse editor output")
                return []
        else:
            return []

    if isinstance(data, dict):
        data = data.get("articles", [])

    scored: list[ScoredArticle] = []
    for item in data:
        if isinstance(item, dict):
            try:
                scored.append(ScoredArticle.model_validate(item))
            except Exception as e:
                log.debug("Skipping malformed scored article: %s", e)

    return scored
