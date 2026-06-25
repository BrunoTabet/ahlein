"""Outbound message delivery (WhatsApp Cloud API).

Designed so a BSP (360dialog / Twilio) could sit in front later — the rest of the app
only calls `send_text(ctx, to, text)`. Outside production (or with no token configured)
this is a no-op that just logs, so the simulator and evals never need a real number.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.db.crypto import decrypt
from app.tenancy.context import TenantContext

logger = logging.getLogger(__name__)

_GRAPH_URL = "https://graph.facebook.com/v21.0"


async def send_text(ctx: TenantContext, to: str, text: str) -> None:
    token_enc = ctx.tenant.whatsapp_token_encrypted
    if not settings.is_production or not token_enc:
        logger.info("[send→%s via %s] %s", to, ctx.name, text)
        return

    token = decrypt(token_enc)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    url = f"{_GRAPH_URL}/{ctx.tenant.phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url, json=payload, headers={"Authorization": f"Bearer {token}"}
        )
    if resp.status_code >= 400:
        logger.error("WhatsApp send failed %s: %s", resp.status_code, resp.text[:200])
