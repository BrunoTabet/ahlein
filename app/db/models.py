"""Row-level multi-tenant schema. EVERY table carries `tenant_id`; every query filters on it.

One Postgres database for all clinics. Clinic content (doctors, services, hours, FAQ,
credentials) lives here as data — adding a clinic or swapping a doctor is a row edit,
never a code change or redeploy.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """One clinic. Owns its own WhatsApp number / WABA — never pooled across clinics."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))

    # WhatsApp Cloud API: every inbound payload carries phone_number_id → tenant.
    phone_number_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    whatsapp_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dubai")

    # Booking adapter selection + its encrypted config (e.g. Cal.com api_key as JSON).
    booking_provider: Mapped[str] = mapped_column(String(32), default="mock")
    booking_config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Inline FAQ for Phase 1 ({"q":..., "a":...}); Phase 3 replaces this with RAG.
    faqs: Mapped[list | None] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    services: Mapped[list["ServiceType"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class ServiceType(Base):
    """A bookable appointment type — the clinic's STRUCTURED knowledge.

    The LLM's job is to map a free-text complaint to one of THESE rows. It must never
    invent a service that is not in the menu.
    """

    __tablename__ = "service_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(255))
    doctor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="AED")

    # Free-text complaint hints the model can use to disambiguate ("finger", "rash", ...).
    trigger_keywords: Mapped[list | None] = mapped_column(JSON, default=list)

    # Adapter-specific routing handle (Cal.com event type id). Opaque to bot logic.
    calcom_event_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="services")


class Appointment(Base):
    """Minimal patient data only: name, phone, chosen slot, complaint CATEGORY.

    No medical records, no free-text medical detail persisted.
    """

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_type_id: Mapped[int] = mapped_column(ForeignKey("service_types.id"))

    patient_name: Mapped[str] = mapped_column(String(255))
    patient_phone: Mapped[str] = mapped_column(String(32), index=True)
    complaint_category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(32), default="booked")
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Phase 3 (RAG): a `documents` table with a pgvector `embedding` column lands here.
# The extension is enabled now (scripts/init_db.py) so that work is drop-in.
