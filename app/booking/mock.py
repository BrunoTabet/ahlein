"""In-memory adapter for local dev, the simulator, and evals — no external calls.

Generates plausible weekday slots (Gulf working week, Sun–Thu) and always confirms
bookings. The seed tenant uses this so the full flow runs with no Cal.com account.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.booking.adapter import Booking, BookingAdapter, PatientRef, Slot
from app.db.models import ServiceType

_SLOT_HOURS = (9, 10, 11, 14, 15)
_GULF_WORKDAYS = {6, 0, 1, 2, 3}  # Python weekday(): Sun=6, Mon=0 ... Thu=3


class MockBookingAdapter(BookingAdapter):
    async def check_availability(
        self, service: ServiceType, date_from: date, date_to: date, tz: str
    ) -> list[Slot]:
        zone = ZoneInfo(tz)
        duration = timedelta(minutes=service.duration_minutes)
        slots: list[Slot] = []
        day = date_from
        while day <= date_to:
            if day.weekday() in _GULF_WORKDAYS:
                for hour in _SLOT_HOURS:
                    start = datetime.combine(day, time(hour), tzinfo=zone)
                    slots.append(Slot(start=start, end=start + duration))
            day += timedelta(days=1)
        return slots

    async def book_appointment(
        self, service: ServiceType, slot_start: datetime, patient: PatientRef, tz: str
    ) -> Booking:
        return Booking(
            reference=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            start=slot_start,
            end=slot_start + timedelta(minutes=service.duration_minutes),
            status="booked",
        )
