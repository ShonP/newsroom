"""Load and manage the editorial profile for the newsroom."""

from __future__ import annotations

from pathlib import Path

from newsroom.log import log

_DEFAULT_PROFILE_PATH = Path("data/editorial_profile.md")

_FALLBACK_PROFILE = """\
Focus: AI, ML, LLMs, open-source AI, developer tools, cloud infrastructure.
Exclude: crypto speculation, consumer gadget reviews, celebrity gossip, clickbait.
Tone: analytical, concise, practitioner-focused. Explain why stories matter.
Preferred sources: TechCrunch, Ars Technica, Hacker News, arXiv, GitHub.
"""


def load_editorial_profile(path: Path | str | None = None) -> str:
    """Load the editorial profile from disk, with a sensible fallback.

    Args:
        path: Override path. Defaults to data/editorial_profile.md.
    """
    target = Path(path) if path else _DEFAULT_PROFILE_PATH

    if target.is_file():
        try:
            content = target.read_text(encoding="utf-8").strip()
            if content:
                log.debug("Loaded editorial profile from %s", target)
                return content
        except Exception as e:
            log.warning("Failed to read editorial profile: %s", e)

    log.debug("Using fallback editorial profile")
    return _FALLBACK_PROFILE
