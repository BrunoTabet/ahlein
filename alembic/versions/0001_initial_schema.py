"""initial schema (tenants, service_types, appointments) + pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-06-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enabled now (no vector columns yet) so the Phase 3 RAG work is drop-in.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        sa.Column("whatsapp_token_encrypted", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Dubai"),
        sa.Column("booking_provider", sa.String(length=32), nullable=False, server_default="mock"),
        sa.Column("booking_config_encrypted", sa.Text(), nullable=True),
        sa.Column("faqs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tenants_phone_number_id", "tenants", ["phone_number_id"], unique=True)

    op.create_table(
        "service_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=False),
        sa.Column("doctor", sa.String(length=255), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="AED"),
        sa.Column("trigger_keywords", sa.JSON(), nullable=True),
        sa.Column("calcom_event_type_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_service_types_tenant_id", "service_types", ["tenant_id"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "service_type_id", sa.Integer(), sa.ForeignKey("service_types.id"), nullable=False
        ),
        sa.Column("patient_name", sa.String(length=255), nullable=False),
        sa.Column("patient_phone", sa.String(length=32), nullable=False),
        sa.Column("complaint_category", sa.String(length=255), nullable=True),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="booked"),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_appointments_tenant_id", "appointments", ["tenant_id"])
    op.create_index("ix_appointments_patient_phone", "appointments", ["patient_phone"])


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("service_types")
    op.drop_table("tenants")
