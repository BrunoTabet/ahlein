"""Normalise a WhatsApp Cloud API webhook payload into a BSP-agnostic InboundMessage list.

Keeping the wire shape isolated here means a BSP (360dialog / Twilio) can be added later
by swapping this parser, with nothing downstream aware of the change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InboundMessage:
    phone_number_id: str   # routing key → tenant
    from_number: str
    text: str
    message_id: str
    profile_name: str | None = None


def parse_webhook(payload: dict) -> list[InboundMessage]:
    messages: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if not phone_number_id:
                continue

            contacts = value.get("contacts", [])
            profile_name = (
                contacts[0].get("profile", {}).get("name") if contacts else None
            )

            for m in value.get("messages", []):
                if m.get("type") != "text":
                    continue  # Phase 1 handles text only.
                messages.append(
                    InboundMessage(
                        phone_number_id=phone_number_id,
                        from_number=m.get("from", ""),
                        text=m.get("text", {}).get("body", ""),
                        message_id=m.get("id", ""),
                        profile_name=profile_name,
                    )
                )
    return messages
