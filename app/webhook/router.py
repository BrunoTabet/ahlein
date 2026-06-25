"""The single WhatsApp webhook. All clinics' messages arrive here."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from app.config import settings
from app.orchestrator import handle_inbound
from app.webhook.parser import parse_webhook

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def verify(request: Request) -> Response:
    """Meta webhook verification handshake."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403, content="verification failed")


@router.post("/webhook")
async def receive(request: Request) -> dict:
    payload = await request.json()
    inbound = parse_webhook(payload)

    # The replies are echoed back for the simulator/evals; the real Cloud API ignores
    # the response body (delivery happens via the outbound sender).
    replies = []
    for msg in inbound:
        result = await handle_inbound(msg)
        if result is not None:
            replies.append(
                {
                    "to": msg.from_number,
                    "reply": result.reply,
                    "handoff": result.handoff,
                    "tool_calls": [c["name"] for c in result.tool_calls],
                }
            )

    return {"status": "ok", "replies": replies}
