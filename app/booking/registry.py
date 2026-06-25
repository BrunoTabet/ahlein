"""Picks the booking adapter for a tenant from `tenant.booking_provider`."""
from __future__ import annotations

from app.booking.adapter import BookingAdapter
from app.booking.calcom import CalComAdapter
from app.booking.mock import MockBookingAdapter

_ADAPTERS: dict[str, type[BookingAdapter]] = {
    "mock": MockBookingAdapter,
    "calcom": CalComAdapter,
}


def get_adapter(provider: str, config: dict | None = None) -> BookingAdapter:
    try:
        cls = _ADAPTERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown booking_provider '{provider}'. Known: {sorted(_ADAPTERS)}"
        ) from None
    return cls(config)
