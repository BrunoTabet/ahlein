"""Create the schema and enable pgvector.

Phase 1 bootstraps via create_all + the pgvector extension. Alembic migrations land in
Phase 2 alongside the admin layer, where schema churn begins.

    python -m scripts.init_db
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("Schema created and pgvector enabled.")


if __name__ == "__main__":
    asyncio.run(main())
