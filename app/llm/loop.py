"""Provider-neutral tool-use loop: classify → slot-fill → check availability → book / hand off.

The loop knows nothing about Gemini vs Claude — it talks to an LLMProvider and keeps a
neutral, JSON-serialisable history (for Redis). Manual loop (not an SDK tool-runner) so we
keep the safety short-circuit, per-turn logging, and full control of history.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider import get_provider
from app.llm.prompts import build_system_prompt
from app.llm.tools import TOOL_SCHEMAS, ToolExecutor
from app.safety.handoff import HANDOFF_MESSAGE, should_force_handoff
from app.tenancy.context import TenantContext

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 6


@dataclass
class LoopResult:
    reply: str
    handoff: bool
    messages: list[dict]                                    # neutral history to persist
    tool_calls: list[dict] = field(default_factory=list)    # [{"name","input"}] for evals/obs
    forced_handoff: bool = False


async def run_loop(
    ctx: TenantContext,
    session: AsyncSession,
    history: list[dict],
    user_text: str,
    patient_phone: str,
    provider_name: str | None = None,
) -> LoopResult:
    # Layer 1 safety: hard keyword screen BEFORE the model. Deterministic, no tokens.
    if should_force_handoff(user_text):
        messages = history + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": HANDOFF_MESSAGE},
        ]
        logger.info("forced handoff (sensitive keyword) for %s", patient_phone)
        return LoopResult(
            reply=HANDOFF_MESSAGE, handoff=True, messages=messages, forced_handoff=True
        )

    provider = get_provider(provider_name)
    system = build_system_prompt(ctx)
    executor = ToolExecutor(ctx, session, patient_phone)

    messages: list[dict] = history + [{"role": "user", "content": user_text}]
    observed: list[dict] = []
    reply = ""

    for _ in range(_MAX_ITERATIONS):
        turn = await provider.complete(system, messages, TOOL_SCHEMAS)
        messages.append(
            {
                "role": "assistant",
                "content": turn.text,
                "tool_calls": [
                    {"id": c.id, "name": c.name, "args": c.args, "signature": c.signature}
                    for c in turn.tool_calls
                ],
            }
        )
        reply = turn.text

        if not turn.tool_calls:
            break

        results = []
        for call in turn.tool_calls:
            observed.append({"name": call.name, "input": call.args})
            output = await executor.run(call.name, call.args)
            results.append({"id": call.id, "name": call.name, "output": output})
        messages.append({"role": "tool", "results": results})

        if executor.handoff:
            reply = HANDOFF_MESSAGE
            messages.append({"role": "assistant", "content": HANDOFF_MESSAGE})
            return LoopResult(
                reply=reply, handoff=True, messages=messages, tool_calls=observed
            )

    if not reply:
        reply = (
            "Sorry, I didn't quite catch that. Could you tell me a bit more about what "
            "you'd like to book?"
        )
    return LoopResult(reply=reply, handoff=False, messages=messages, tool_calls=observed)
