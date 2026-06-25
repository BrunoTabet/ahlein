"""Glue: inbound message → tenant → session → LLM loop → persist → send.

This is the one place the pieces meet. Returns the bot's reply (and loop metadata) so
the simulator, evals, and the webhook can all drive the same path.
"""
from __future__ import annotations

import logging

from app.conversation import session as session_store
from app.conversation import window
from app.db.session import get_session
from app.llm.loop import LoopResult, run_loop
from app.messaging.sender import send_text
from app.tenancy.resolver import resolve_tenant
from app.webhook.parser import InboundMessage

logger = logging.getLogger(__name__)


async def handle_inbound(
    msg: InboundMessage, provider_name: str | None = None
) -> LoopResult | None:
    async with get_session() as db:
        ctx = await resolve_tenant(db, msg.phone_number_id)
        if ctx is None:
            logger.warning("no tenant for phone_number_id=%s; ignoring", msg.phone_number_id)
            return None

        tenant_id = ctx.tenant.id
        await window.mark_inbound(tenant_id, msg.from_number)
        history = await session_store.load_history(tenant_id, msg.from_number)

        result = await run_loop(
            ctx=ctx,
            session=db,
            history=history,
            user_text=msg.text,
            patient_phone=msg.from_number,
            provider_name=provider_name,
        )

        await session_store.save_history(tenant_id, msg.from_number, result.messages)
        await send_text(ctx, msg.from_number, result.reply)

        if result.handoff:
            logger.info("HANDOFF tenant=%s phone=%s", tenant_id, msg.from_number)
        return result
