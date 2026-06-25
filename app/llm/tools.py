"""Tool schemas + executor.

The bot exposes exactly four tools to Claude. `check_availability` and
`book_appointment` go through the per-tenant BookingAdapter — the LLM never knows
whether Cal.com, an external API, or browser automation is behind them.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.adapter import BookingError, PatientRef
from app.db.models import Appointment
from app.safety.handoff import HANDOFF_MESSAGE
from app.tenancy.context import TenantContext

logger = logging.getLogger(__name__)

_MAX_SLOTS_RETURNED = 6
_DEFAULT_LOOKAHEAD_DAYS = 14

TOOL_SCHEMAS = [
    {
        "name": "select_service",
        "description": (
            "Map the patient's described need to one service from the menu. Returns the "
            "service's details. Only valid service ids from the menu are accepted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer", "description": "id from the SERVICE MENU"}
            },
            "required": ["service_id"],
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Get available appointment slots for a service. Optionally constrain by a date "
            "range (YYYY-MM-DD). Returns a short list of bookable start times."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "date_from": {"type": "string", "description": "YYYY-MM-DD, optional"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD, optional"},
            },
            "required": ["service_id"],
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Book a confirmed appointment. Call only after the patient has chosen a slot "
            "returned by check_availability and given their full name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "slot_start": {
                    "type": "string",
                    "description": "ISO 8601 start time from check_availability",
                },
                "patient_name": {"type": "string"},
            },
            "required": ["service_id", "slot_start", "patient_name"],
        },
    },
    {
        "name": "handoff_to_human",
        "description": (
            "Escalate to a human team member. Use for serious/sensitive complaints, "
            "uncertainty, or anything outside booking and basic FAQs. Do NOT give medical "
            "advice — hand off instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "brief internal reason"},
            },
            "required": ["reason"],
        },
    },
]


class ToolExecutor:
    """Stateful per-conversation tool runner. Holds the tenant context + DB session."""

    def __init__(self, ctx: TenantContext, session: AsyncSession, patient_phone: str) -> None:
        self.ctx = ctx
        self.session = session
        self.patient_phone = patient_phone
        self.handoff = False
        self.handoff_reason: str | None = None

    async def run(self, name: str, args: dict) -> dict:
        handler = {
            "select_service": self._select_service,
            "check_availability": self._check_availability,
            "book_appointment": self._book_appointment,
            "handoff_to_human": self._handoff,
        }.get(name)
        if handler is None:
            return {"error": f"unknown tool '{name}'"}
        try:
            return await handler(args)
        except BookingError as exc:
            logger.warning("booking error in %s: %s", name, exc)
            return {"error": str(exc)}

    async def _select_service(self, args: dict) -> dict:
        service = self.ctx.service_by_id(int(args["service_id"]))
        if service is None:
            return {"error": "No such service id in this clinic's menu."}
        return {
            "service_id": service.id,
            "name": service.name,
            "department": service.department,
            "doctor": service.doctor,
            "duration_minutes": service.duration_minutes,
            "price": float(service.price) if service.price is not None else None,
            "currency": service.currency,
        }

    async def _check_availability(self, args: dict) -> dict:
        service = self.ctx.service_by_id(int(args["service_id"]))
        if service is None:
            return {"error": "No such service id."}
        tz = self.ctx.timezone
        today = datetime.now(ZoneInfo(tz)).date()
        date_from = _parse_date(args.get("date_from"), default=today)
        date_to = _parse_date(
            args.get("date_to"), default=date_from + timedelta(days=_DEFAULT_LOOKAHEAD_DAYS)
        )
        slots = await self.ctx.adapter.check_availability(service, date_from, date_to, tz)
        upcoming = slots[:_MAX_SLOTS_RETURNED]
        return {
            "service": service.name,
            "slots": [
                {
                    "slot_start": s.start.isoformat(),
                    "label": s.start.strftime("%a %d %b, %I:%M %p"),
                }
                for s in upcoming
            ],
        }

    async def _book_appointment(self, args: dict) -> dict:
        service = self.ctx.service_by_id(int(args["service_id"]))
        if service is None:
            return {"error": "No such service id."}
        slot_start = datetime.fromisoformat(args["slot_start"])
        patient = PatientRef(name=args["patient_name"].strip(), phone=self.patient_phone)

        booking = await self.ctx.adapter.book_appointment(
            service, slot_start, patient, self.ctx.timezone
        )

        # Persist minimal data only: name, phone, slot, complaint CATEGORY (= department).
        self.session.add(
            Appointment(
                tenant_id=self.ctx.tenant.id,
                service_type_id=service.id,
                patient_name=patient.name,
                patient_phone=patient.phone,
                complaint_category=service.department,
                slot_start=booking.start,
                slot_end=booking.end,
                status=booking.status,
                external_ref=booking.reference,
            )
        )
        await self.session.commit()

        return {
            "status": "confirmed",
            "reference": booking.reference,
            "when": booking.start.strftime("%A %d %B, %I:%M %p"),
            "service": service.name,
        }

    async def _handoff(self, args: dict) -> dict:
        self.handoff = True
        self.handoff_reason = args.get("reason", "")
        return {"status": "handed_off", "message_to_patient": HANDOFF_MESSAGE}


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default
