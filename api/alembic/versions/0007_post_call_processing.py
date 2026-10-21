"""post-call processing metadata

Revision ID: 0007_post_call_processing
Revises: 0006_messaging_reminders
Create Date: 2026-10-21

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_post_call_processing"
down_revision: str | Sequence[str] | None = "0006_messaging_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("livekit_room_name", sa.Text(), nullable=True))
    op.add_column(
        "calls",
        sa.Column(
            "recording_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "calls",
        sa.Column(
            "usage_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("calls", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("calls", sa.Column("outcome", sa.Text(), nullable=True))
    op.add_column(
        "calls",
        sa.Column(
            "cost_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "calls",
        sa.Column(
            "post_call_status",
            sa.Text(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "calls",
        sa.Column(
            "post_call_error",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    op.add_column(
        "calls",
        sa.Column(
            "evaluation_status",
            sa.Text(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "calls",
        sa.Column(
            "evaluation_error",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_calls_clinic_room",
        "calls",
        ["clinic_id", "livekit_room_name"],
    )
    op.create_check_constraint(
        "ck_calls_outcome",
        "calls",
        "outcome IS NULL OR outcome IN ('booked', 'enquiry', 'transferred', 'dropped')",
    )
    op.create_check_constraint(
        "ck_calls_post_call_status",
        "calls",
        "post_call_status IN ('pending', 'processing', 'completed', 'failed')",
    )
    op.create_check_constraint(
        "ck_calls_evaluation_status",
        "calls",
        "evaluation_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_calls_evaluation_status", "calls", type_="check")
    op.drop_constraint("ck_calls_post_call_status", "calls", type_="check")
    op.drop_constraint("ck_calls_outcome", "calls", type_="check")
    op.drop_constraint("uq_calls_clinic_room", "calls", type_="unique")
    op.drop_column("calls", "evaluation_error")
    op.drop_column("calls", "evaluation_status")
    op.drop_column("calls", "post_call_error")
    op.drop_column("calls", "post_call_status")
    op.drop_column("calls", "cost_breakdown")
    op.drop_column("calls", "outcome")
    op.drop_column("calls", "summary")
    op.drop_column("calls", "usage_metrics")
    op.drop_column("calls", "recording_meta")
    op.drop_column("calls", "livekit_room_name")
