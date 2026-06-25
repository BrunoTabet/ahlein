"""Phase 3 stub: tenant-scoped RAG over FAQ/policy docs (pgvector).

The interface is fixed now so the LLM loop can call retrieval without knowing whether
it's backed by inline FAQs (Phase 1) or embedded documents (Phase 3). Phase 1 answers
FAQs from the inline `tenant.faqs` injected into the prompt; this lands the embedding
pipeline (doc upload → chunk → embed → tenant-scoped similarity search) behind the same
shape.
"""
from __future__ import annotations

from app.tenancy.context import TenantContext


async def retrieve(ctx: TenantContext, query: str, k: int = 4) -> list[str]:  # noqa: ARG001
    raise NotImplementedError("RAG retrieval lands in Phase 3.")
