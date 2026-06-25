"""Seed ONE hardcoded clinic for Phase 1 (no admin UI yet).

Idempotent: re-running upserts the tenant by phone_number_id. Uses the `mock` booking
adapter so the full flow runs with no Cal.com account.

    python -m seeds.seed_tenant
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import delete, select

from app.db.crypto import encrypt
from app.db.models import ServiceType, Tenant
from app.db.session import get_session

# This is the value WhatsApp puts in webhook payloads. The simulator uses the same.
SEED_PHONE_NUMBER_ID = "100000000000001"

_SERVICES = [
    {
        "name": "Orthopedic consultation",
        "department": "Orthopedics",
        "doctor": "Dr. Sara Haddad",
        "duration_minutes": 30,
        "price": 350,
        "trigger_keywords": ["finger", "hand", "wrist", "knee", "joint", "bone", "fracture",
                              "sprain", "back pain", "اصبع", "كسر", "مفصل", "ظهر"],
        "calcom_event_type_id": 101,
    },
    {
        "name": "Dermatology consultation",
        "department": "Dermatology",
        "doctor": "Dr. Omar Khalil",
        "duration_minutes": 20,
        "price": 300,
        "trigger_keywords": ["skin", "rash", "acne", "mole", "derma", "جلد", "حبوب", "طفح"],
        "calcom_event_type_id": 102,
    },
    {
        "name": "General practitioner visit",
        "department": "General Medicine",
        "doctor": "Dr. Layla Mansour",
        "duration_minutes": 20,
        "price": 250,
        "trigger_keywords": ["fever", "cold", "flu", "checkup", "general", "حرارة", "كشف عام"],
        "calcom_event_type_id": 103,
    },
]

_FAQS = [
    {"q": "Where do I park?",
     "a": "Free visitor parking is available on level B2 of the building; take the lift to "
          "the 3rd floor reception."},
    {"q": "Do you accept insurance?",
     "a": "We accept most major UAE insurers including Daman, AXA, and MetLife. Bring your "
          "insurance card to reception."},
    {"q": "What are your opening hours?",
     "a": "We are open Sunday to Thursday, 9:00 AM to 6:00 PM."},
    {"q": "What is your cancellation policy?",
     "a": "Please give at least 24 hours notice to cancel or reschedule, free of charge."},
]


async def main() -> None:
    async with get_session() as db:
        existing = (
            await db.execute(
                select(Tenant).where(Tenant.phone_number_id == SEED_PHONE_NUMBER_ID)
            )
        ).scalar_one_or_none()

        if existing:
            await db.execute(
                delete(ServiceType).where(ServiceType.tenant_id == existing.id)
            )
            tenant = existing
            tenant.name = "Gulf Care Clinic"
            tenant.faqs = _FAQS
        else:
            tenant = Tenant(
                name="Gulf Care Clinic",
                phone_number_id=SEED_PHONE_NUMBER_ID,
                timezone="Asia/Dubai",
                booking_provider="mock",
                faqs=_FAQS,
            )
            db.add(tenant)
            await db.flush()

        # Example of how a Cal.com tenant's encrypted credentials would be stored.
        # The seed uses the mock adapter, so this config is illustrative only.
        tenant.booking_config_encrypted = encrypt(json.dumps({"api_key": "REPLACE_ME"}))

        for s in _SERVICES:
            db.add(ServiceType(tenant_id=tenant.id, **s))

        await db.commit()
        print(f"Seeded tenant '{tenant.name}' (id={tenant.id}, "
              f"phone_number_id={SEED_PHONE_NUMBER_ID}) with {len(_SERVICES)} services.")


if __name__ == "__main__":
    asyncio.run(main())
