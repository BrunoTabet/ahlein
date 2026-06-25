from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.booking.mock import MockBookingAdapter
from app.booking.adapter import PatientRef

TZ = "Asia/Dubai"


def _service(duration=30):
    return SimpleNamespace(duration_minutes=duration, name="Test", calcom_event_type_id=None)


@pytest.mark.asyncio
async def test_check_availability_returns_workday_slots():
    adapter = MockBookingAdapter()
    # 2026-06-07 is a Sunday (Gulf workweek start); 2026-06-11 a Thursday.
    slots = await adapter.check_availability(_service(), date(2026, 6, 7), date(2026, 6, 11), TZ)
    assert slots, "expected slots on Gulf workdays"
    assert all(s.end > s.start for s in slots)
    # Friday 2026-06-12 / Saturday 2026-06-13 are weekend → excluded.
    assert all(s.start.weekday() not in (4, 5) for s in slots)


@pytest.mark.asyncio
async def test_book_returns_reference():
    adapter = MockBookingAdapter()
    booking = await adapter.book_appointment(
        _service(), datetime(2026, 6, 7, 9, 0), PatientRef("Jane", "9715000"), TZ
    )
    assert booking.reference.startswith("MOCK-")
    assert booking.status == "booked"
