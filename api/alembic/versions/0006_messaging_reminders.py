"""add clinic messaging settings, message logs, and appointment language

Revision ID: 0006_messaging_reminders
Revises: 0005_human_transfer_callbacks
Create Date: 2026-10-21

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_messaging_reminders"
down_revision: str | Sequence[str] | None = "0005_human_transfer_callbacks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("language", sa.Text(), server_default=sa.text("'en'"), nullable=False),
    )
    op.create_table(
        "clinic_messaging_settings",
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "confirmation_whatsapp_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "confirmation_sms_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "reminders_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "reminder_24h_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "reminder_2h_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "reminder_channel",
            sa.Text(),
            server_default=sa.text("'whatsapp'"),
            nullable=False,
        ),
        sa.Column("default_language", sa.Text(), server_default=sa.text("'en'"), nullable=False),
        sa.Column(
            "confirmation_template_en", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "confirmation_template_hi", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "reminder_24h_template_en", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "reminder_24h_template_hi", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "reminder_2h_template_en", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "reminder_2h_template_hi", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
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
            "default_language IN ('en', 'hi')",
            name="ck_messaging_language",
        ),
        sa.CheckConstraint(
            "reminder_channel IN ('whatsapp', 'sms')",
            name="ck_messaging_reminder_channel",
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("clinic_id"),
    )
    op.create_table(
        "message_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("appointment_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), server_default=sa.text("''"), nullable=False),
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
        sa.CheckConstraint("channel IN ('whatsapp', 'sms')", name="ck_message_logs_channel"),
        sa.CheckConstraint(
            "kind IN ('confirmation', 'reminder_24h', 'reminder_2h')",
            name="ck_message_logs_kind",
        ),
        sa.CheckConstraint(
            "status IN ('sent', 'failed', 'skipped')",
            name="ck_message_logs_status",
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_logs_clinic_created_at",
        "message_logs",
        ["clinic_id", "created_at"],
    )
    op.create_index(
        "ix_message_logs_appointment_kind",
        "message_logs",
        ["appointment_id", "kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_logs_appointment_kind", table_name="message_logs")
    op.drop_index("ix_message_logs_clinic_created_at", table_name="message_logs")
    op.drop_table("message_logs")
    op.drop_table("clinic_messaging_settings")
    op.drop_column("appointments", "language")
