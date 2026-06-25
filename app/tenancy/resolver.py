"""phone_number_id → TenantContext.

A single WhatsApp webhook receives all clinics' messages. The inbound payload's
phone_number_id is the only routing key; we resolve it to a tenant, load that tenant's
config from the DB, decrypt its credentials, and build the adapter. Everything after
this is tenant-scoped.

Phase 1 loads fresh from the DB on every message (correctness over speed) so a data
edit takes effect with no redeploy. Phase 2 adds a short-lived cache.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.booking.registry import get_adapter
from app.db.crypto import decrypt
from app.db.models import Tenant
from app.tenancy.context import TenantContext


async def resolve_tenant(session: AsyncSession, phone_number_id: str) -> TenantContext | None:
    result = await session.execute(
        select(Tenant)
        .where(Tenant.phone_number_id == phone_number_id)
        .options(selectinload(Tenant.services))
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        return None

    booking_config: dict = {}
    if tenant.booking_config_encrypted:
        booking_config = json.loads(decrypt(tenant.booking_config_encrypted))

    adapter = get_adapter(tenant.booking_provider, booking_config)
    active_services = [s for s in tenant.services if s.active]

    return TenantContext(
        tenant=tenant,
        services=active_services,
        adapter=adapter,
        timezone=tenant.timezone,
        faqs=tenant.faqs or [],
    )
