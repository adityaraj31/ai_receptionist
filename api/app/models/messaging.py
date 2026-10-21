from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..messaging.templates import default_templates
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .appointment import Appointment
    from .clinic import Clinic

_DEFAULTS = default_templates()


class ClinicMessagingSettings(Base, TimestampMixin):
    __tablename__ = "clinic_messaging_settings"
    __table_args__ = (
        CheckConstraint("default_language IN ('en', 'hi')", name="ck_messaging_language"),
        CheckConstraint(
            "reminder_channel IN ('whatsapp', 'sms')",
            name="ck_messaging_reminder_channel",
        ),
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), primary_key=True
    )
    confirmation_whatsapp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    confirmation_sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_24h_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_2h_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_channel: Mapped[str] = mapped_column(Text, nullable=False, default="whatsapp")
    default_language: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    confirmation_template_en: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULTS["confirmation_template_en"]
    )
    confirmation_template_hi: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULTS["confirmation_template_hi"]
    )
    reminder_24h_template_en: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULTS["reminder_24h_template_en"]
    )
    reminder_24h_template_hi: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULTS["reminder_24h_template_hi"]
    )
    reminder_2h_template_en: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULTS["reminder_2h_template_en"]
    )
    reminder_2h_template_hi: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULTS["reminder_2h_template_hi"]
    )

    clinic: Mapped[Clinic] = relationship(back_populates="messaging_settings")


class MessageLog(Base, TimestampMixin):
    __tablename__ = "message_logs"
    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp', 'sms')", name="ck_message_logs_channel"),
        CheckConstraint(
            "kind IN ('confirmation', 'reminder_24h', 'reminder_2h')",
            name="ck_message_logs_kind",
        ),
        CheckConstraint(
            "status IN ('sent', 'failed', 'skipped')",
            name="ck_message_logs_status",
        ),
        Index("ix_message_logs_clinic_created_at", "clinic_id", "created_at"),
        Index("ix_message_logs_appointment_kind", "appointment_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    appointment_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    clinic: Mapped[Clinic] = relationship()
    appointment: Mapped[Appointment | None] = relationship()
