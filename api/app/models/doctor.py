from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .appointment import Appointment
    from .availability import AvailabilityRule, TimeOff
    from .clinic import Clinic


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"
    __table_args__ = (UniqueConstraint("clinic_id", "name", name="uq_doctors_clinic_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    specialization: Mapped[str] = mapped_column(Text, nullable=False, default="")
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("'{}'::text[]")
    )
    fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    clinic: Mapped[Clinic] = relationship(back_populates="doctors")
    availability_rules: Mapped[list[AvailabilityRule]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    time_off: Mapped[list[TimeOff]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="doctor")
