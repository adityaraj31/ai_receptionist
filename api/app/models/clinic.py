from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .appointment import Appointment
    from .call import Call
    from .callback import CallbackTask
    from .doctor import Doctor
    from .patient import Patient
    from .staff import AgentApiKey, StaffUser


class Clinic(Base, TimestampMixin):
    __tablename__ = "clinics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Asia/Kolkata")
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    front_desk_number: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    staff_users: Mapped[list[StaffUser]] = relationship(back_populates="clinic")
    doctors: Mapped[list[Doctor]] = relationship(back_populates="clinic")
    patients: Mapped[list[Patient]] = relationship(back_populates="clinic")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="clinic")
    agent_api_keys: Mapped[list[AgentApiKey]] = relationship(back_populates="clinic")
    calls: Mapped[list[Call]] = relationship(back_populates="clinic")
    callback_tasks: Mapped[list[CallbackTask]] = relationship(back_populates="clinic")
