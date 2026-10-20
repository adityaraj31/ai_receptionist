from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .doctor import Doctor


class AvailabilityRule(Base, TimestampMixin):
    __tablename__ = "availability_rules"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_rules_doctor_window",
        ),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_availability_weekday"),
        CheckConstraint("end_time > start_time", name="ck_availability_time_order"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 240", name="ck_availability_slot_minutes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    doctor: Mapped[Doctor] = relationship(back_populates="availability_rules")


class TimeOff(Base, TimestampMixin):
    __tablename__ = "time_off"
    __table_args__ = (CheckConstraint("ends_at > starts_at", name="ck_time_off_order"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    doctor: Mapped[Doctor] = relationship(back_populates="time_off")
