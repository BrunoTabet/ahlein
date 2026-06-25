"""Anthropic Claude provider. Converts neutral history → Anthropic Messages format."""
from __future__ import annotations

from functools import lru_cache

from anthropic import AsyncAnthropic

from app.config import settings
from app.llm.provider import LLMProvider
from app.llm.types import AssistantTurn, ToolCall

_MAX_TOKENS = 1024


@lru_cache
def _client() -> AsyncAnthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


class ClaudeProvider(LLMProvider):
    name = "claude"

    async def complete(
        self, system: str, history: list[dict], tools: list[dict]
    ) -> AssistantTurn:
        resp = await _client().messages.create(
            model=settings.classifier_model,
            max_tokens=_MAX_TOKENS,
            system=system,
            tools=tools,  # already {name, description, input_schema}
            messages=_to_anthropic(history),
        )
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, args=dict(block.input)))
        return AssistantTurn(text="\n".join(text_parts).strip(), tool_calls=calls)


def _to_anthropic(history: list[dict]) -> list[dict]:
    messages: list[dict] = []
    for entry in history:
        role = entry["role"]
        if role == "user":
            messages.append({"role": "user", "content": entry["content"]})
        elif role == "assistant":
            blocks: list[dict] = []
            if entry.get("content"):
                blocks.append({"type": "text", "text": entry["content"]})
            for tc in entry.get("tool_calls", []):
                blocks.append(
                    {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["args"]}
                )
            messages.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            import json

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r["id"],
                            "content": json.dumps(r["output"], ensure_ascii=False),
                        }
                        for r in entry["results"]
                    ],
                }
            )
    return messages
