"""OpenAI chat completion client factory."""

from __future__ import annotations

from agent_framework_openai import OpenAIChatCompletionClient

from newsroom.config import get_settings


def get_chat_client() -> OpenAIChatCompletionClient:
    """Create an OpenAIChatCompletionClient configured from environment."""
    settings = get_settings()
    return OpenAIChatCompletionClient(
        model=settings.model,
        api_key=settings.azure_api_key,
        base_url=settings.openai_base_url,
    )
