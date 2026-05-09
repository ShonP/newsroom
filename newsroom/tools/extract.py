"""Full article text extraction tool using trafilatura."""

from __future__ import annotations

import json

import httpx
from agent_framework._tools import tool

from newsroom.log import log

_MAX_CONTENT_LENGTH = 5000
_TIMEOUT = 20


def extract_article_text(url: str) -> str:
    """Extract the main text content from a web page.

    Returns the extracted text, or an empty string on failure.
    This is the plain function — use for direct pipeline calls.
    """
    try:
        import trafilatura
    except ImportError:
        log.warning("trafilatura not installed — skipping extraction")
        return ""

    try:
        resp = httpx.get(
            url,
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OpenClawBot/0.1)"},
        )
        resp.raise_for_status()
    except Exception as e:
        log.debug("Fetch failed for extraction: %s — %s", url[:80], e)
        return ""

    try:
        text = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not text:
            return ""
        return text[:_MAX_CONTENT_LENGTH]
    except Exception as e:
        log.debug("Extraction failed for %s: %s", url[:80], e)
        return ""


@tool
def extract_article(url: str) -> str:
    """Extract the full article text from a URL for deeper analysis.

    Args:
        url: The article URL to extract text from.
    """
    text = extract_article_text(url)
    if text:
        return json.dumps({"url": url, "content": text, "length": len(text)})
    return json.dumps({"url": url, "content": "", "error": "Extraction failed"})
