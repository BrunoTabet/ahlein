"""Cal.com v2 booking adapter — the first real adapter.

Verified against Cal.com API v2 docs (June 2026):
  - GET  /v2/slots    ?eventTypeId=&start=&end=&timeZone=
        → {"status":"success","data":{"YYYY-MM-DD":[{"start": "...ISO..."}]}}
  - POST /v2/bookings {start(UTC ISO), eventTypeId, attendee:{name,email,timeZone,phoneNumber,language}}
        → {"status":"success","data":{"id","uid","status","start","end"}}

Cal.com pins behaviour to a date via the `cal-api-version` header, which differs per
endpoint. These constants are the well-known stable versions — bump them deliberately
and re-test against a real account before pointing a clinic at it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

import httpx

from app.booking.adapter import Booking, BookingAdapter, BookingError, PatientRef, Slot
from app.db.models import ServiceType

_BASE_URL = "https://api.cal.com/v2"
_SLOTS_API_VERSION = "2024-09-04"
_BOOKINGS_API_VERSION = "2024-08-13"
_TIMEOUT = 15.0


class CalComAdapter(BookingAdapter):
    @property
    def _api_key(self) -> str:
        key = self.config.get("api_key")
        if not key:
            raise BookingError("Cal.com adapter is missing 'api_key' in tenant booking config.")
        return key

    def _event_type_id(self, service: ServiceType) -> int:
        if service.calcom_event_type_id is None:
            raise BookingError(
                f"Service '{service.name}' has no calcom_event_type_id configured."
            )
        return service.calcom_event_type_id

    async def check_availability(
        self, service: ServiceType, date_from: date, date_to: date, tz: str
    ) -> list[Slot]:
        params = {
            "eventTypeId": self._event_type_id(service),
            "start": date_from.isoformat(),
            "end": date_to.isoformat(),
            "timeZone": tz,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "cal-api-version": _SLOTS_API_VERSION,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE_URL}/slots", params=params, headers=headers)
        if resp.status_code >= 400:
            raise BookingError(f"Cal.com slots error {resp.status_code}: {resp.text[:200]}")

        data = resp.json().get("data", {})
        duration = timedelta(minutes=service.duration_minutes)
        slots: list[Slot] = []
        for _day, day_slots in sorted(data.items()):
            for entry in day_slots:
                start = datetime.fromisoformat(entry["start"]).astimezone(ZoneInfo(tz))
                slots.append(Slot(start=start, end=start + duration))
        return slots

    async def book_appointment(
        self, service: ServiceType, slot_start: datetime, patient: PatientRef, tz: str
    ) -> Booking:
        # Cal.com requires an attendee email; synthesise a stable, non-PII placeholder
        # from the phone number when the patient hasn't supplied one.
        digits = "".join(c for c in patient.phone if c.isdigit())
        email = self.config.get("attendee_email") or f"wa-{digits}@no-reply.invalid"
        body = {
            "start": slot_start.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
            "eventTypeId": self._event_type_id(service),
            "attendee": {
                "name": patient.name,
                "email": email,
                "timeZone": tz,
                "phoneNumber": patient.phone,
                "language": "en",
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "cal-api-version": _BOOKINGS_API_VERSION,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{_BASE_URL}/bookings", json=body, headers=headers)
        if resp.status_code >= 400:
            raise BookingError(f"Cal.com booking error {resp.status_code}: {resp.text[:200]}")

        data = resp.json().get("data", {})
        start = datetime.fromisoformat(data["start"]).astimezone(ZoneInfo(tz))
        end = datetime.fromisoformat(data["end"]).astimezone(ZoneInfo(tz))
        return Booking(
            reference=str(data.get("uid") or data.get("id")),
            start=start,
            end=end,
            status=data.get("status", "booked"),
        )
