from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .appointment import Appointment
    from .clinic import Clinic


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("clinic_id", "phone", name="uq_patients_clinic_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)

    clinic: Mapped[Clinic] = relationship(back_populates="patients")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")
