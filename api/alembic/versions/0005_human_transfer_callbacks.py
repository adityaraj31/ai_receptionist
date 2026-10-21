"""add front desk number and callback tasks

Revision ID: 0005_human_transfer_callbacks
Revises: 0004_faq_chunks
Create Date: 2026-10-21

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_human_transfer_callbacks"
down_revision: str | Sequence[str] | None = "0004_faq_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clinics", sa.Column("front_desk_number", sa.Text(), nullable=True))
    op.create_table(
        "callback_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("caller_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("message", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'agent'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'contacted', 'done', 'cancelled')",
            name="ck_callback_tasks_status",
        ),
        sa.CheckConstraint(
            "source IN ('agent', 'staff')",
            name="ck_callback_tasks_source",
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_callback_tasks_clinic_created_at",
        "callback_tasks",
        ["clinic_id", "created_at"],
    )
    op.create_index(
        "ix_callback_tasks_clinic_status",
        "callback_tasks",
        ["clinic_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_callback_tasks_clinic_status", table_name="callback_tasks")
    op.drop_index("ix_callback_tasks_clinic_created_at", table_name="callback_tasks")
    op.drop_table("callback_tasks")
    op.drop_column("clinics", "front_desk_number")
