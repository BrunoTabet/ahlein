"""Human-handoff path. This is medical software: the bot gives NO medical advice.

Two layers, defence-in-depth:
  1. A hard keyword screen here that fires BEFORE the LLM for clearly serious/sensitive
     complaints — deterministic, can't be talked around, costs no tokens.
  2. The LLM's own `handoff_to_human` tool for uncertainty or anything outside its flows
     (see app/llm/tools.py + the system prompt).
"""
from __future__ import annotations

HANDOFF_MESSAGE = (
    "Thank you for reaching out. So I can make sure you get the right care, "
    "let me connect you with a member of our team who will follow up with you shortly."
)

# Serious / sensitive terms that must never be triaged by the bot. English + Arabic.
# Conservative on purpose — false positives hand off to a human, which is the safe failure.
_SENSITIVE_TERMS = (
    "cancer", "tumor", "tumour", "chest pain", "heart attack", "stroke",
    "suicide", "suicidal", "kill myself", "self harm", "self-harm",
    "overdose", "bleeding heavily", "can't breathe", "cant breathe",
    "unconscious", "seizure", "pregnan",  # pregnancy / pregnant
    "سرطان", "ورم", "نوبة قلبية", "سكتة", "انتحار", "نزيف",
)


def should_force_handoff(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _SENSITIVE_TERMS)
