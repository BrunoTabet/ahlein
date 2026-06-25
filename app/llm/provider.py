"""LLM provider interface + registry.

Mirrors the booking adapter: the booking *loop* depends only on this interface, so the
underlying model is a config choice (LLM_PROVIDER) — or, later, a per-tenant choice —
without touching loop or orchestration logic.
"""
from __future__ import annotations

import abc
from functools import lru_cache

from app.config import settings
from app.llm.types import AssistantTurn


class LLMProvider(abc.ABC):
    name: str

    @abc.abstractmethod
    async def complete(
        self, system: str, history: list[dict], tools: list[dict]
    ) -> AssistantTurn:
        """Run one model turn over neutral history; return text + any tool calls."""


@lru_cache
def _build(provider_name: str) -> LLMProvider:
    if provider_name == "gemini":
        from app.llm.providers.gemini import GeminiProvider

        return GeminiProvider()
    if provider_name == "claude":
        from app.llm.providers.claude import ClaudeProvider

        return ClaudeProvider()
    raise ValueError(f"Unknown LLM_PROVIDER '{provider_name}'. Known: gemini, claude")


def get_provider(provider_name: str | None = None) -> LLMProvider:
    return _build(provider_name or settings.llm_provider)
