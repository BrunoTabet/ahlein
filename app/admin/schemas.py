"""Pydantic request/response models for the admin REST API.

Secrets (WhatsApp token, Cal.com api_key) are write-only inputs — they are never echoed
back. Responses report only whether a credential is set.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceIn(BaseModel):
    name: str
    department: str
    doctor: str | None = None
    duration_minutes: int = 30
    price: float | None = None
    currency: str = "AED"
    trigger_keywords: list[str] = Field(default_factory=list)
    calcom_event_type_id: int | None = None
    active: bool = True


class ServiceOut(ServiceIn):
    id: int
    tenant_id: int


class TenantIn(BaseModel):
    name: str
    phone_number_id: str
    timezone: str = "Asia/Dubai"
    booking_provider: str = "mock"
    faqs: list[dict] = Field(default_factory=list)
    # Write-only credentials.
    whatsapp_token: str | None = None
    booking_api_key: str | None = None


class TenantUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    booking_provider: str | None = None
    faqs: list[dict] | None = None
    whatsapp_token: str | None = None
    booking_api_key: str | None = None


class TenantOut(BaseModel):
    id: int
    name: str
    phone_number_id: str
    timezone: str
    booking_provider: str
    faqs: list[dict]
    whatsapp_token_set: bool
    booking_api_key_set: bool
    services: list[ServiceOut] = Field(default_factory=list)
