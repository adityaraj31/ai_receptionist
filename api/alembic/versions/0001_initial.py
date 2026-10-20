"""initial clinic schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "clinics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "timezone",
            sa.Text(),
            server_default=sa.text("'Asia/Kolkata'"),
            nullable=False,
        ),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "staff_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'staff'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_staff_users_email"),
    )
    op.create_index("ix_staff_users_clinic_id", "staff_users", ["clinic_id"])

    op.create_table(
        "agent_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), server_default=sa.text("'default'"), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_agent_api_keys_key_hash"),
    )
    op.create_index("ix_agent_api_keys_clinic_id", "agent_api_keys", ["clinic_id"])

    op.create_table(
        "doctors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("specialization", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "fee",
            sa.Numeric(10, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "name", name="uq_doctors_clinic_name"),
    )
    op.create_index("ix_doctors_clinic_id", "doctors", ["clinic_id"])

    op.create_table(
        "availability_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), server_default=sa.text("15"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint("end_time > start_time", name="ck_availability_time_order"),
        sa.CheckConstraint("slot_minutes BETWEEN 5 AND 240", name="ck_availability_slot_minutes"),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_availability_weekday"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "doctor_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_rules_doctor_window",
        ),
    )
    op.create_index("ix_availability_rules_doctor_id", "availability_rules", ["doctor_id"])

    op.create_table(
        "time_off",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
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
        sa.CheckConstraint("ends_at > starts_at", name="ck_time_off_order"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_off_doctor_id", "time_off", ["doctor_id"])
    op.execute(
        """
        ALTER TABLE time_off
        ADD CONSTRAINT ex_time_off_no_overlap
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        """
    )

    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "phone", name="uq_patients_clinic_phone"),
    )
    op.create_index("ix_patients_clinic_id", "patients", ["clinic_id"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'booked'"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'staff'"), nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_by_staff_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint("ends_at > starts_at", name="ck_appointments_time_order"),
        sa.CheckConstraint("source IN ('staff', 'agent')", name="ck_appointments_source"),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled', 'completed', 'no_show')",
            name="ck_appointments_status",
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_staff_id"], ["staff_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_appointments_clinic_starts_at",
        "appointments",
        ["clinic_id", "starts_at"],
    )
    op.create_index(
        "ix_appointments_doctor_starts_at",
        "appointments",
        ["doctor_id", "starts_at"],
    )
    op.create_index(
        "uq_appointments_doctor_start_active",
        "appointments",
        ["doctor_id", "starts_at"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
    )
    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT ex_appointments_no_overlap
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (status <> 'cancelled')
        """
    )

    op.create_table(
        "calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("from_number", sa.Text(), nullable=True),
        sa.Column("to_number", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), server_default=sa.text("'inbound'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'completed'"), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("cost", sa.Numeric(10, 4), nullable=True),
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
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calls_clinic_id", "calls", ["clinic_id"])
    op.create_index("ix_calls_started_at", "calls", ["started_at"])

    op.create_table(
        "transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcripts_call_id", "transcripts", ["call_id"])

    op.create_table(
        "call_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_events_call_id", "call_events", ["call_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(6, 3), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluations_call_id", "evaluations", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluations_call_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_call_events_call_id", table_name="call_events")
    op.drop_table("call_events")
    op.drop_index("ix_transcripts_call_id", table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_index("ix_calls_started_at", table_name="calls")
    op.drop_index("ix_calls_clinic_id", table_name="calls")
    op.drop_table("calls")
    op.execute("ALTER TABLE appointments DROP CONSTRAINT ex_appointments_no_overlap")
    op.drop_index("uq_appointments_doctor_start_active", table_name="appointments")
    op.drop_index("ix_appointments_doctor_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_clinic_starts_at", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_patients_clinic_id", table_name="patients")
    op.drop_table("patients")
    op.execute("ALTER TABLE time_off DROP CONSTRAINT ex_time_off_no_overlap")
    op.drop_index("ix_time_off_doctor_id", table_name="time_off")
    op.drop_table("time_off")
    op.drop_index("ix_availability_rules_doctor_id", table_name="availability_rules")
    op.drop_table("availability_rules")
    op.drop_index("ix_doctors_clinic_id", table_name="doctors")
    op.drop_table("doctors")
    op.drop_index("ix_agent_api_keys_clinic_id", table_name="agent_api_keys")
    op.drop_table("agent_api_keys")
    op.drop_index("ix_staff_users_clinic_id", table_name="staff_users")
    op.drop_table("staff_users")
    op.drop_table("clinics")
