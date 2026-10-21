from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .clinic import Clinic


class Call(Base, TimestampMixin):
    __tablename__ = "calls"
    __table_args__ = (
        UniqueConstraint("clinic_id", "livekit_room_name", name="uq_calls_clinic_room"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('booked', 'enquiry', 'transferred', 'dropped')",
            name="ck_calls_outcome",
        ),
        CheckConstraint(
            "post_call_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_calls_post_call_status",
        ),
        CheckConstraint(
            "evaluation_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')",
            name="ck_calls_evaluation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL")
    )
    from_number: Mapped[str | None] = mapped_column(Text)
    to_number: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text, nullable=False, default="inbound")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")
    language: Mapped[str | None] = mapped_column(Text)
    livekit_room_name: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    recording_url: Mapped[str | None] = mapped_column(Text)
    recording_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    usage_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    cost_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    post_call_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    post_call_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evaluation_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    evaluation_error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    clinic: Mapped[Clinic] = relationship(back_populates="calls")
    transcripts: Mapped[list[Transcript]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    events: Mapped[list[CallEvent]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text)

    call: Mapped[Call] = relationship(back_populates="transcripts")


class CallEvent(Base, TimestampMixin):
    __tablename__ = "call_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    call: Mapped[Call] = relationship(back_populates="events")


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    call: Mapped[Call] = relationship(back_populates="evaluations")
