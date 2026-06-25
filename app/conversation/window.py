"""24-hour customer-service window tracking.

Inbound messages within 24h of the patient's last message are free-form and free to
reply to. Outside it, business-initiated messages need approved utility templates
(Phase 4). We record the last-inbound timestamp per (tenant, phone) so Phase 4 can
decide free-form vs template without a schema change.
"""
from __future__ import annotations

import time

import redis.asyncio as redis

from app.config import settings

_WINDOW_SECONDS = 24 * 60 * 60

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def _key(tenant_id: int, phone: str) -> str:
    return f"window:{tenant_id}:{phone}"


async def mark_inbound(tenant_id: int, phone: str) -> None:
    await _redis().set(_key(tenant_id, phone), str(int(time.time())), ex=_WINDOW_SECONDS)


async def is_open(tenant_id: int, phone: str) -> bool:
    raw = await _redis().get(_key(tenant_id, phone))
    if raw is None:
        return False
    return (time.time() - int(raw)) < _WINDOW_SECONDS
