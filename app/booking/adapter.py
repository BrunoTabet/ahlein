"""The booking boundary.

The bot only ever calls `check_availability()` and `book_appointment()`. Which concrete
adapter runs behind this interface is chosen per tenant (see registry.py). New adapters
(external API, browser automation) are added beside calcom.py WITHOUT touching bot logic.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import date, datetime

from app.db.models import ServiceType


@dataclass
class Slot:
    start: datetime
    end: datetime


@dataclass
class PatientRef:
    name: str
    phone: str


@dataclass
class Booking:
    reference: str
    start: datetime
    end: datetime
    status: str


class BookingError(Exception):
    """Raised when an adapter cannot fulfil an availability/booking request."""


class BookingAdapter(abc.ABC):
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @abc.abstractmethod
    async def check_availability(
        self, service: ServiceType, date_from: date, date_to: date, tz: str
    ) -> list[Slot]:
        ...

    @abc.abstractmethod
    async def book_appointment(
        self, service: ServiceType, slot_start: datetime, patient: PatientRef, tz: str
    ) -> Booking:
        ...
