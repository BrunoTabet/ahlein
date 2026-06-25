"""Admin CRUD operations — the single place that writes clinic data.

Both the REST API and the web UI call these. Credentials are encrypted here on write
(via app.db.crypto) so plaintext secrets never reach the database.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.crypto import encrypt
from app.db.models import ServiceType, Tenant


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.services)).order_by(Tenant.id)
    )
    return list(result.scalars().all())


async def get_tenant(db: AsyncSession, tenant_id: int) -> Tenant | None:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.services))
    )
    return result.scalar_one_or_none()


def _encode_booking_config(api_key: str) -> str:
    return encrypt(json.dumps({"api_key": api_key}))


async def create_tenant(
    db: AsyncSession,
    *,
    name: str,
    phone_number_id: str,
    timezone: str = "Asia/Dubai",
    booking_provider: str = "mock",
    faqs: list[dict] | None = None,
    whatsapp_token: str | None = None,
    booking_api_key: str | None = None,
) -> Tenant:
    tenant = Tenant(
        name=name,
        phone_number_id=phone_number_id,
        timezone=timezone,
        booking_provider=booking_provider,
        faqs=faqs or [],
        whatsapp_token_encrypted=encrypt(whatsapp_token) if whatsapp_token else None,
        booking_config_encrypted=_encode_booking_config(booking_api_key)
        if booking_api_key
        else None,
    )
    db.add(tenant)
    await db.commit()
    return await get_tenant(db, tenant.id)  # type: ignore[return-value]


async def update_tenant(db: AsyncSession, tenant_id: int, **fields) -> Tenant | None:
    tenant = await get_tenant(db, tenant_id)
    if tenant is None:
        return None

    for attr in ("name", "timezone", "booking_provider", "faqs"):
        value = fields.get(attr)
        if value is not None:
            setattr(tenant, attr, value)

    if fields.get("whatsapp_token"):
        tenant.whatsapp_token_encrypted = encrypt(fields["whatsapp_token"])
    if fields.get("booking_api_key"):
        tenant.booking_config_encrypted = _encode_booking_config(fields["booking_api_key"])

    await db.commit()
    return await get_tenant(db, tenant_id)


async def create_service(db: AsyncSession, tenant_id: int, **fields) -> ServiceType:
    service = ServiceType(tenant_id=tenant_id, **fields)
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


async def update_service(db: AsyncSession, service_id: int, **fields) -> ServiceType | None:
    service = await db.get(ServiceType, service_id)
    if service is None:
        return None
    for attr, value in fields.items():
        if value is not None:
            setattr(service, attr, value)
    await db.commit()
    await db.refresh(service)
    return service
