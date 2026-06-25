"""POST a fake WhatsApp webhook payload to the running app — no real WhatsApp/phone needed.

Start the app (`uvicorn app.main:app --reload`), seed the tenant, then:

    python -m scripts.simulate_message "my finger hurts"
    python -m scripts.simulate_message "my finger hurts" --from 971500000001

Keeps the same --from across calls to continue a multi-turn conversation (session state
lives in Redis keyed by tenant + phone).
"""
from __future__ import annotations

import argparse
import json

import httpx

from seeds.seed_tenant import SEED_PHONE_NUMBER_ID


def build_payload(text: str, from_number: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+971 4 000 0000",
                                "phone_number_id": SEED_PHONE_NUMBER_ID,
                            },
                            "contacts": [
                                {"profile": {"name": "Test Patient"}, "wa_id": from_number}
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": "wamid.TEST",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a WhatsApp inbound message.")
    parser.add_argument("text", help="the patient's message")
    parser.add_argument("--from", dest="from_number", default="971500000000")
    parser.add_argument("--url", default="http://localhost:8000/webhook")
    args = parser.parse_args()

    payload = build_payload(args.text, args.from_number)
    resp = httpx.post(args.url, json=payload, timeout=60.0)
    resp.raise_for_status()
    body = resp.json()

    for reply in body.get("replies", []):
        tag = " [HANDOFF]" if reply["handoff"] else ""
        tools = f"  (tools: {', '.join(reply['tool_calls'])})" if reply["tool_calls"] else ""
        print(f"\nBot{tag}: {reply['reply']}{tools}")
    if not body.get("replies"):
        print(json.dumps(body, indent=2))


if __name__ == "__main__":
    main()
