"""FastAPI entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.admin.api import router as admin_api_router
from app.admin.ui import router as admin_ui_router
from app.config import settings
from app.webhook.router import router as webhook_router

logging.basicConfig(level=settings.log_level)

app = FastAPI(title="Ahlein", version="0.2.0")
app.include_router(webhook_router)
app.include_router(admin_api_router)
app.include_router(admin_ui_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
