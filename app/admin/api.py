"""Admin REST API — manage clinics + services as data. Secured by the admin key.

    curl -H "X-Admin-Key: $ADMIN_API_KEY" localhost:8000/admin/api/tenants
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service
from app.admin.auth import require_admin_key
from app.admin.schemas import ServiceIn, ServiceOut, TenantIn, TenantOut, TenantUpdate
from app.db.models import ServiceType, Tenant
from app.db.session import get_db

router = APIRouter(prefix="/admin/api", dependencies=[Depends(require_admin_key)])


def _service_out(s: ServiceType) -> ServiceOut:
    return ServiceOut(
        id=s.id,
        tenant_id=s.tenant_id,
        name=s.name,
        department=s.department,
        doctor=s.doctor,
        duration_minutes=s.duration_minutes,
        price=float(s.price) if s.price is not None else None,
        currency=s.currency,
        trigger_keywords=s.trigger_keywords or [],
        calcom_event_type_id=s.calcom_event_type_id,
        active=s.active,
    )


def _tenant_out(t: Tenant) -> TenantOut:
    return TenantOut(
        id=t.id,
        name=t.name,
        phone_number_id=t.phone_number_id,
        timezone=t.timezone,
        booking_provider=t.booking_provider,
        faqs=t.faqs or [],
        whatsapp_token_set=bool(t.whatsapp_token_encrypted),
        booking_api_key_set=bool(t.booking_config_encrypted),
        services=[_service_out(s) for s in t.services],
    )


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    return [_tenant_out(t) for t in await service.list_tenants(db)]


@router.post("/tenants", response_model=TenantOut, status_code=201)
async def create_tenant(body: TenantIn, db: AsyncSession = Depends(get_db)):
    tenant = await service.create_tenant(
        db,
        name=body.name,
        phone_number_id=body.phone_number_id,
        timezone=body.timezone,
        booking_provider=body.booking_provider,
        faqs=body.faqs,
        whatsapp_token=body.whatsapp_token,
        booking_api_key=body.booking_api_key,
    )
    return _tenant_out(tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: int, db: AsyncSession = Depends(get_db)):
    tenant = await service.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(404, "tenant not found")
    return _tenant_out(tenant)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
async def update_tenant(tenant_id: int, body: TenantUpdate, db: AsyncSession = Depends(get_db)):
    tenant = await service.update_tenant(db, tenant_id, **body.model_dump(exclude_unset=True))
    if tenant is None:
        raise HTTPException(404, "tenant not found")
    return _tenant_out(tenant)


@router.post("/tenants/{tenant_id}/services", response_model=ServiceOut, status_code=201)
async def add_service(tenant_id: int, body: ServiceIn, db: AsyncSession = Depends(get_db)):
    if await service.get_tenant(db, tenant_id) is None:
        raise HTTPException(404, "tenant not found")
    created = await service.create_service(db, tenant_id, **body.model_dump())
    return _service_out(created)


@router.patch("/services/{service_id}", response_model=ServiceOut)
async def update_service(service_id: int, body: ServiceIn, db: AsyncSession = Depends(get_db)):
    updated = await service.update_service(db, service_id, **body.model_dump())
    if updated is None:
        raise HTTPException(404, "service not found")
    return _service_out(updated)
