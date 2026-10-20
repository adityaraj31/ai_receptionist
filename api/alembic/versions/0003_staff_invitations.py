"""add staff invitations

Revision ID: 0003_staff_invitations
Revises: 0002_enable_pgvector
Create Date: 2026-10-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_staff_invitations"
down_revision: str | Sequence[str] | None = "0002_enable_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'staff'"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by_staff_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["invited_by_staff_id"],
            ["staff_users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_staff_invitations_token_hash"),
    )
    op.create_index("ix_staff_invitations_clinic_id", "staff_invitations", ["clinic_id"])
    op.create_index("ix_staff_invitations_email", "staff_invitations", ["email"])


def downgrade() -> None:
    op.drop_index("ix_staff_invitations_email", table_name="staff_invitations")
    op.drop_index("ix_staff_invitations_clinic_id", table_name="staff_invitations")
    op.drop_table("staff_invitations")
