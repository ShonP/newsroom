"""URL normalization and SQLite-backed deduplication layer."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from newsroom.log import log
from newsroom.models.article import Article

# Parameters to strip from URLs during normalization
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "ref",
        "source",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ncid",
        "sr_share",
        "tag",
        "_hsenc",
        "_hsmi",
    }
)

_FUZZY_THRESHOLD = 0.75
_DEDUP_WINDOW_HOURS = 72

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_articles (
    url_hash    TEXT PRIMARY KEY,
    title_hash  TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    first_seen  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_title_hash ON seen_articles(title_hash);
CREATE INDEX IF NOT EXISTS idx_first_seen ON seen_articles(first_seen);
"""


def normalize_url(url: str) -> str:
    """Normalize a URL by stripping tracking params, fragments, trailing slashes."""
    parsed = urlparse(url)

    # Strip fragment
    # Strip trailing slash from path (but keep "/" for root)
    path = parsed.path.rstrip("/") or "/"

    # Remove tracking query params
    params = parse_qs(parsed.query, keep_blank_values=False)
    cleaned = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
    query = urlencode(cleaned, doseq=True)

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            query,
            "",  # no fragment
        )
    )


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:32]


def _normalize_title(title: str) -> str:
    """Lowercase, strip whitespace and punctuation for comparison."""
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


class DedupDB:
    """SQLite-backed article deduplication database."""

    def __init__(self, db_path: str | Path = "data/dedup.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.executescript(_DB_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def _cutoff(self) -> float:
        return time.time() - (_DEDUP_WINDOW_HOURS * 3600)

    def is_duplicate(self, url: str, title: str) -> bool:
        """Check if an article has been seen recently (within TTL window)."""
        norm_url = normalize_url(url)
        url_hash = _hash(norm_url)
        cutoff = self._cutoff()

        # Exact URL match
        row = self._conn.execute(
            "SELECT 1 FROM seen_articles WHERE url_hash = ? AND first_seen > ?",
            (url_hash, cutoff),
        ).fetchone()
        if row:
            return True

        # Fuzzy title match against recent entries
        norm_title = _normalize_title(title)
        if not norm_title:
            return False

        title_hash = _hash(norm_title)
        # Check exact title hash first (fast path)
        row = self._conn.execute(
            "SELECT 1 FROM seen_articles WHERE title_hash = ? AND first_seen > ?",
            (title_hash, cutoff),
        ).fetchone()
        if row:
            return True

        # Fuzzy match against recent titles
        rows = self._conn.execute(
            "SELECT title FROM seen_articles WHERE first_seen > ?",
            (cutoff,),
        ).fetchall()
        for (existing_title,) in rows:
            ratio = SequenceMatcher(
                None,
                norm_title,
                _normalize_title(existing_title),
            ).ratio()
            if ratio >= _FUZZY_THRESHOLD:
                return True

        return False

    def mark_seen(self, article: Article) -> None:
        """Record an article as seen."""
        norm_url = normalize_url(article.url)
        url_hash = _hash(norm_url)
        norm_title = _normalize_title(article.title)
        title_hash = _hash(norm_title)

        self._conn.execute(
            """INSERT OR IGNORE INTO seen_articles
               (url_hash, title_hash, title, url, source, first_seen)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url_hash, title_hash, article.title, article.url, article.source, time.time()),
        )
        self._conn.commit()

    def mark_seen_batch(self, articles: list[Article]) -> None:
        """Record multiple articles as seen."""
        now = time.time()
        rows = []
        for a in articles:
            norm_url = normalize_url(a.url)
            url_hash = _hash(norm_url)
            norm_title = _normalize_title(a.title)
            title_hash = _hash(norm_title)
            rows.append((url_hash, title_hash, a.title, a.url, a.source, now))

        self._conn.executemany(
            """INSERT OR IGNORE INTO seen_articles
               (url_hash, title_hash, title, url, source, first_seen)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

    def cleanup(self, max_age_hours: int = 168) -> int:
        """Remove entries older than max_age_hours. Returns count removed."""
        cutoff = time.time() - (max_age_hours * 3600)
        cursor = self._conn.execute(
            "DELETE FROM seen_articles WHERE first_seen < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict[str, int]:
        """Return basic stats about the dedup database."""
        total = self._conn.execute("SELECT COUNT(*) FROM seen_articles").fetchone()[0]
        cutoff = self._cutoff()
        recent = self._conn.execute(
            "SELECT COUNT(*) FROM seen_articles WHERE first_seen > ?",
            (cutoff,),
        ).fetchone()[0]
        return {"total_entries": total, "recent_entries": recent, "window_hours": _DEDUP_WINDOW_HOURS}


def dedup_articles(articles: list[Article], db: DedupDB) -> list[Article]:
    """Filter out articles already seen in previous runs (cross-run dedup)."""
    unique: list[Article] = []
    dupes = 0
    for article in articles:
        if db.is_duplicate(article.url, article.title):
            dupes += 1
        else:
            unique.append(article)

    if dupes:
        log.info("Dedup: removed %d cross-run duplicates, %d remaining", dupes, len(unique))
    return unique
