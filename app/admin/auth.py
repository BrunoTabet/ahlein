"""Admin auth — a single shared key (Phase 2). Real multi-user/RBAC is later.

Two entry points share one key:
  - REST API: `X-Admin-Key` header.
  - Web UI:   an HttpOnly cookie set at login.
Comparisons are constant-time.
"""
from __future__ import annotations

import hmac

from fastapi import Cookie, Header, HTTPException, status

from app.config import settings

COOKIE_NAME = "ahlein_admin"


def _valid(candidate: str | None) -> bool:
    if not candidate:
        return False
    return hmac.compare_digest(candidate, settings.admin_api_key)


async def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Dependency for REST endpoints."""
    if not _valid(x_admin_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


def is_logged_in(cookie_value: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> bool:
    """Dependency for UI routes — returns whether the session cookie is valid."""
    return _valid(cookie_value)
