"""Offline provider smoke test — verifies LLM wiring + tool-calling + Arabic with NO DB/Redis.

    python -m scripts.smoke_llm                         # uses LLM_PROVIDER
    python -m scripts.smoke_llm --provider gemini "احجز موعد لإصبعي"
    python -m scripts.smoke_llm --provider claude "my finger hurts"

Sends one turn with a minimal system prompt + the real tool schemas and prints the
model's text and any tool calls. A correct run picks select_service for the finger case.
"""
from __future__ import annotations

import argparse
import asyncio

from app.config import settings
from app.llm.provider import get_provider
from app.llm.tools import TOOL_SCHEMAS

_SYSTEM = (
    "You are the booking assistant for a clinic. Map the patient's need to ONE service "
    "from this menu using select_service (only these ids exist):\n"
    "- id=1 | Orthopedic consultation | dept: Orthopedics | hints: finger, hand, bone\n"
    "- id=2 | Dermatology consultation | dept: Dermatology | hints: skin, rash, acne\n"
    "Never invent services. For serious/sensitive complaints, call handoff_to_human. "
    "Reply in the patient's language."
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("message", nargs="?", default="can I book for my finger?")
    parser.add_argument("--provider", default=settings.llm_provider)
    args = parser.parse_args()

    provider = get_provider(args.provider)
    history = [{"role": "user", "content": args.message}]
    turn = await provider.complete(_SYSTEM, history, TOOL_SCHEMAS)

    print(f"\nprovider: {provider.name}")
    print(f"message:  {args.message}")
    print(f"text:     {turn.text or '(none)'}")
    if turn.tool_calls:
        for c in turn.tool_calls:
            print(f"tool:     {c.name}({c.args})")
    else:
        print("tool:     (none)")


if __name__ == "__main__":
    asyncio.run(main())
