"""Live conversation state in Redis, scoped per (tenant, patient phone).

Stores the running message history (Anthropic message dicts) so the stateless LLM loop
can resume a multi-turn booking. TTL-bounded; trimmed to recent turns.
"""
from __future__ import annotations

import json

import redis.asyncio as redis

from app.config import settings

_SESSION_TTL_SECONDS = 24 * 60 * 60
_MAX_MESSAGES = 40

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def _key(tenant_id: int, phone: str) -> str:
    return f"session:{tenant_id}:{phone}"


async def load_history(tenant_id: int, phone: str) -> list[dict]:
    raw = await _redis().get(_key(tenant_id, phone))
    return json.loads(raw) if raw else []


async def save_history(tenant_id: int, phone: str, messages: list[dict]) -> None:
    trimmed = messages[-_MAX_MESSAGES:]
    await _redis().set(
        _key(tenant_id, phone), json.dumps(trimmed), ex=_SESSION_TTL_SECONDS
    )


async def clear_history(tenant_id: int, phone: str) -> None:
    await _redis().delete(_key(tenant_id, phone))
