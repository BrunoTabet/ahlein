"""Run the LLM eval suite on demand against the seeded clinic.

Drives the same orchestrator path the webhook uses (in-process, no running server).
Requires DB + Redis + ANTHROPIC_API_KEY. The cancer→handoff case runs offline (the
keyword screen short-circuits before any API call).

    python -m evals.run_evals                # uses LLM_PROVIDER from .env
    python -m evals.run_evals --provider gemini
    python -m evals.run_evals --provider claude
    python -m evals.run_evals --provider all # bake-off across both
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from app.config import settings
from app.conversation import session as session_store
from app.db.session import get_session
from app.orchestrator import handle_inbound
from app.tenancy.context import TenantContext
from app.tenancy.resolver import resolve_tenant
from app.webhook.parser import InboundMessage
from seeds.seed_tenant import SEED_PHONE_NUMBER_ID

CASES_FILE = Path(__file__).parent / "cases.yaml"


def _evaluate(case: dict, result, department: str | None) -> tuple[bool, str]:
    expect = case["expect"]
    kind = expect["kind"]
    names = [c["name"] for c in result.tool_calls]
    booking_names = {"select_service", "check_availability", "book_appointment"}

    if kind == "handoff":
        return (result.handoff, "expected handoff")

    if kind == "select_service":
        if "select_service" not in names:
            return (False, "expected a select_service call")
        if "department" in expect and department != expect["department"]:
            return (False, f"expected department {expect['department']!r}, got {department!r}")
        return (True, "")

    if kind == "faq":
        if result.handoff:
            return (False, "expected an FAQ answer, got handoff")
        sub = expect.get("reply_contains", "").lower()
        if sub and sub not in result.reply.lower():
            return (False, f"reply did not contain {sub!r}")
        return (True, "")

    if kind == "clarify":
        if result.handoff:
            return (False, "expected a clarifying question, got handoff")
        if booking_names & set(names):
            return (False, f"expected no booking tools, got {names}")
        return (True, "")

    return (False, f"unknown expect.kind {kind!r}")


async def run_provider(provider: str, cases: list[dict], ctx: TenantContext) -> int:
    print(f"\n=== provider: {provider} ===")
    passed = 0
    for i, case in enumerate(cases):
        phone = f"eval-{provider}-{i}"
        # Fresh conversation per case (clears any state left by a previous run).
        await session_store.clear_history(ctx.tenant.id, phone)

        result = await handle_inbound(
            InboundMessage(
                phone_number_id=SEED_PHONE_NUMBER_ID,
                from_number=phone,
                text=case["message"],
                message_id=f"eval-{i}",
            ),
            provider_name=provider,
        )

        department = None
        sel = next((c for c in result.tool_calls if c["name"] == "select_service"), None)
        if sel is not None:
            service = ctx.service_by_id(int(sel["input"]["service_id"]))
            department = service.department if service else None

        ok, why = _evaluate(case, result, department)
        passed += ok
        mark = "✓" if ok else "✗"
        print(f"{mark} {case['name']}{'' if ok else f' — {why}'}")
        print(f"    reply: {result.reply[:120]}")

    print(f"{provider}: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


async def run(provider_arg: str) -> int:
    cases = yaml.safe_load(CASES_FILE.read_text())
    providers = ["gemini", "claude"] if provider_arg == "all" else [provider_arg]

    async with get_session() as db:
        ctx: TenantContext | None = await resolve_tenant(db, SEED_PHONE_NUMBER_ID)
    if ctx is None:
        print("Tenant not found — run `python -m seeds.seed_tenant` first.")
        return 1

    exit_code = 0
    for provider in providers:
        exit_code |= await run_provider(provider, cases, ctx)
    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", default=settings.llm_provider, choices=["gemini", "claude", "all"]
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.provider)))
