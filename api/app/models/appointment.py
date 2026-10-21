from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .clinic import Clinic
    from .doctor import Doctor
    from .patient import Patient
    from .staff import StaffUser


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointments_time_order"),
        CheckConstraint(
            "status IN ('booked', 'cancelled', 'completed', 'no_show')",
            name="ck_appointments_status",
        ),
        CheckConstraint("source IN ('staff', 'agent')", name="ck_appointments_source"),
        Index(
            "uq_appointments_doctor_start_active",
            "doctor_id",
            "starts_at",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
        ),
        Index("ix_appointments_clinic_starts_at", "clinic_id", "starts_at"),
        Index("ix_appointments_doctor_starts_at", "doctor_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="booked")
    source: Mapped[str] = mapped_column(Text, nullable=False, default="staff")
    language: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )

    clinic: Mapped[Clinic] = relationship(back_populates="appointments")
    doctor: Mapped[Doctor] = relationship(back_populates="appointments", lazy="selectin")
    patient: Mapped[Patient] = relationship(back_populates="appointments", lazy="selectin")
    created_by_staff: Mapped[StaffUser | None] = relationship()
