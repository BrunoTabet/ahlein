"""Server-rendered admin web UI at /admin — login + clinic/service management.

No JS framework: plain HTML forms posting to these routes. Shares the CRUD layer
(app.admin.service) and the single admin key (app.admin.auth) with the REST API.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service
from app.admin.auth import COOKIE_NAME, is_logged_in
from app.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

_LOGIN = RedirectResponse(url="/admin/login", status_code=303)


def _csv_to_list(value: str | None) -> list[str]:
    return [k.strip() for k in (value or "").split(",") if k.strip()]


def _opt_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _opt_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def _parse_faqs(raw: str | None) -> list[dict]:
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    error = "Invalid key" if request.query_params.get("error") else None
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login")
async def login(key: str = Form(...)):
    from app.admin.auth import _valid

    if not _valid(key):
        return RedirectResponse(url="/admin/login?error=1", status_code=303)
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        key,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=8 * 60 * 60,
    )
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/admin/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("", response_class=HTMLResponse)
async def tenants_page(
    request: Request, authed: bool = Depends(is_logged_in), db: AsyncSession = Depends(get_db)
):
    if not authed:
        return _LOGIN
    tenants = await service.list_tenants(db)
    return templates.TemplateResponse(request, "tenants.html", {"tenants": tenants})


@router.post("/tenants")
async def create_tenant(
    authed: bool = Depends(is_logged_in),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    phone_number_id: str = Form(...),
    timezone: str = Form("Asia/Dubai"),
    booking_provider: str = Form("mock"),
    booking_api_key: str = Form(""),
    whatsapp_token: str = Form(""),
):
    if not authed:
        return _LOGIN
    tenant = await service.create_tenant(
        db,
        name=name,
        phone_number_id=phone_number_id,
        timezone=timezone,
        booking_provider=booking_provider,
        booking_api_key=booking_api_key or None,
        whatsapp_token=whatsapp_token or None,
    )
    return RedirectResponse(url=f"/admin/tenants/{tenant.id}", status_code=303)


@router.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def tenant_detail(
    tenant_id: int,
    request: Request,
    authed: bool = Depends(is_logged_in),
    db: AsyncSession = Depends(get_db),
):
    if not authed:
        return _LOGIN
    tenant = await service.get_tenant(db, tenant_id)
    if tenant is None:
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request,
        "tenant_detail.html",
        {"t": tenant, "faqs_json": json.dumps(tenant.faqs or [], ensure_ascii=False, indent=2)},
    )


@router.post("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    authed: bool = Depends(is_logged_in),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    timezone: str = Form(...),
    booking_provider: str = Form(...),
    faqs: str = Form(""),
    booking_api_key: str = Form(""),
    whatsapp_token: str = Form(""),
):
    if not authed:
        return _LOGIN
    await service.update_tenant(
        db,
        tenant_id,
        name=name,
        timezone=timezone,
        booking_provider=booking_provider,
        faqs=_parse_faqs(faqs),
        booking_api_key=booking_api_key or None,
        whatsapp_token=whatsapp_token or None,
    )
    return RedirectResponse(url=f"/admin/tenants/{tenant_id}", status_code=303)


@router.post("/tenants/{tenant_id}/services")
async def add_service(
    tenant_id: int,
    authed: bool = Depends(is_logged_in),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    department: str = Form(...),
    doctor: str = Form(""),
    duration_minutes: int = Form(30),
    price: str = Form(""),
    currency: str = Form("AED"),
    trigger_keywords: str = Form(""),
    calcom_event_type_id: str = Form(""),
):
    if not authed:
        return _LOGIN
    await service.create_service(
        db,
        tenant_id,
        name=name,
        department=department,
        doctor=doctor or None,
        duration_minutes=duration_minutes,
        price=_opt_float(price),
        currency=currency,
        trigger_keywords=_csv_to_list(trigger_keywords),
        calcom_event_type_id=_opt_int(calcom_event_type_id),
    )
    return RedirectResponse(url=f"/admin/tenants/{tenant_id}", status_code=303)


@router.post("/services/{service_id}/toggle")
async def toggle_service(
    service_id: int,
    tenant_id: int = Form(...),
    active: str = Form(...),
    authed: bool = Depends(is_logged_in),
    db: AsyncSession = Depends(get_db),
):
    if not authed:
        return _LOGIN
    await service.update_service(db, service_id, active=(active == "true"))
    return RedirectResponse(url=f"/admin/tenants/{tenant_id}", status_code=303)
