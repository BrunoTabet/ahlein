"""FastAPI entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import settings
from app.webhook.router import router as webhook_router

logging.basicConfig(level=settings.log_level)

app = FastAPI(title="Clinic WhatsApp Bot", version="0.1.0")
app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
