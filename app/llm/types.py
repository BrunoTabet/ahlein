"""Provider-neutral types for the LLM loop.

The conversation history stored in Redis and passed to providers is a list of plain
dicts in this neutral shape, so it's provider-agnostic (you can switch Gemini↔Claude
without rewriting history). Each provider converts it to its own wire format per call.

Neutral history entries:
  {"role": "user",      "content": "<text>"}
  {"role": "assistant", "content": "<text>", "tool_calls": [{"id","name","args"}]}
  {"role": "tool",      "results": [{"id","name","output": <dict>}]}
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict
    # Opaque provider metadata that must be replayed verbatim (Gemini 3 "thought
    # signatures", base64-encoded). None for providers that don't use it.
    signature: str | None = None


@dataclass
class AssistantTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
