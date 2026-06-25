"""Google Gemini provider. Converts neutral history → Gemini `contents`.

Gemini ingests audio natively, which is why it's the lead candidate for the future voice
phase — that work feeds the audio Part in here instead of a transcribed text Part, with
no change to the loop above.
"""
from __future__ import annotations

import base64
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import settings
from app.llm.provider import LLMProvider
from app.llm.types import AssistantTurn, ToolCall


@lru_cache
def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=settings.gemini_api_key)


class GeminiProvider(LLMProvider):
    name = "gemini"

    async def complete(
        self, system: str, history: list[dict], tools: list[dict]
    ) -> AssistantTurn:
        tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["input_schema"],
                )
                for t in tools
            ]
        )
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[tool],
            # We drive the loop ourselves; don't let the SDK auto-execute anything.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        resp = await _client().aio.models.generate_content(
            model=settings.gemini_model,
            contents=_to_gemini(history),
            config=config,
        )

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        candidate = resp.candidates[0] if resp.candidates else None
        parts = candidate.content.parts if candidate and candidate.content else []
        for i, part in enumerate(parts or []):
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc is not None:
                # Gemini 3 attaches a "thought signature" to the function-call part that
                # must be replayed verbatim on the next turn, or the API 400s.
                sig = getattr(part, "thought_signature", None)
                calls.append(
                    ToolCall(
                        id=f"{fc.name}-{i}",  # Gemini has no call ids; synthesise a stable one
                        name=fc.name,
                        args=dict(fc.args or {}),
                        signature=base64.b64encode(sig).decode() if sig else None,
                    )
                )
        return AssistantTurn(text="\n".join(text_parts).strip(), tool_calls=calls)


def _to_gemini(history: list[dict]) -> list[types.Content]:
    contents: list[types.Content] = []
    for entry in history:
        role = entry["role"]
        if role == "user":
            contents.append(
                types.Content(role="user", parts=[types.Part(text=entry["content"])])
            )
        elif role == "assistant":
            parts: list[types.Part] = []
            if entry.get("content"):
                parts.append(types.Part(text=entry["content"]))
            for tc in entry.get("tool_calls", []):
                sig = tc.get("signature")
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(name=tc["name"], args=tc["args"]),
                        thought_signature=base64.b64decode(sig) if sig else None,
                    )
                )
            contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            # Gemini matches function responses by name; ids are not used here.
            parts = [
                types.Part.from_function_response(name=r["name"], response=r["output"])
                for r in entry["results"]
            ]
            contents.append(types.Content(role="user", parts=parts))
    return contents
