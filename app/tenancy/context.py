"""The per-tenant view that everything downstream of webhook resolution is scoped to."""
from __future__ import annotations

from dataclasses import dataclass

from app.booking.adapter import BookingAdapter
from app.db.models import ServiceType, Tenant


@dataclass
class TenantContext:
    tenant: Tenant
    services: list[ServiceType]
    adapter: BookingAdapter
    timezone: str
    faqs: list[dict]

    @property
    def name(self) -> str:
        return self.tenant.name

    def service_by_id(self, service_id: int) -> ServiceType | None:
        return next((s for s in self.services if s.id == service_id), None)
