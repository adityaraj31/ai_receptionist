from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .clinic import Clinic


class CallbackTask(Base, TimestampMixin):
    __tablename__ = "callback_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'contacted', 'done', 'cancelled')",
            name="ck_callback_tasks_status",
        ),
        CheckConstraint("source IN ('agent', 'staff')", name="ck_callback_tasks_source"),
        Index("ix_callback_tasks_clinic_created_at", "clinic_id", "created_at"),
        Index("ix_callback_tasks_clinic_status", "clinic_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    caller_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    source: Mapped[str] = mapped_column(Text, nullable=False, default="agent")

    clinic: Mapped[Clinic] = relationship(back_populates="callback_tasks")
