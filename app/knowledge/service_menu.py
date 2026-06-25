"""Renders a tenant's structured service menu + inline FAQ for injection into the prompt.

This is knowledge-as-data: the menu comes straight from the DB rows, so the same shared
LLM serves every clinic with no per-clinic training or fine-tuning.
"""
from __future__ import annotations

from app.tenancy.context import TenantContext


def render_service_menu(ctx: TenantContext) -> str:
    if not ctx.services:
        return "(No services configured.)"
    lines = []
    for s in ctx.services:
        price = f"{s.price:.0f} {s.currency}" if s.price is not None else "price on request"
        keywords = ", ".join(s.trigger_keywords or []) or "—"
        doctor = f", with {s.doctor}" if s.doctor else ""
        lines.append(
            f"- id={s.id} | {s.name} | dept: {s.department}{doctor} "
            f"| {s.duration_minutes} min | {price} | hints: {keywords}"
        )
    return "\n".join(lines)


def render_faqs(ctx: TenantContext) -> str:
    if not ctx.faqs:
        return "(No FAQs configured.)"
    return "\n".join(f"- Q: {f['q']}\n  A: {f['a']}" for f in ctx.faqs)
