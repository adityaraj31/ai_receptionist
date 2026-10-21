from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .common import ORMModel

Language = Literal["en", "hi"]
Channel = Literal["whatsapp", "sms"]


class MessagingSettingsRead(ORMModel):
    clinic_id: UUID
    confirmation_whatsapp_enabled: bool
    confirmation_sms_enabled: bool
    reminders_enabled: bool
    reminder_24h_enabled: bool
    reminder_2h_enabled: bool
    reminder_channel: Channel
    default_language: Language
    confirmation_template_en: str
    confirmation_template_hi: str
    reminder_24h_template_en: str
    reminder_24h_template_hi: str
    reminder_2h_template_en: str
    reminder_2h_template_hi: str


class MessagingSettingsUpdate(BaseModel):
    confirmation_whatsapp_enabled: bool | None = None
    confirmation_sms_enabled: bool | None = None
    reminders_enabled: bool | None = None
    reminder_24h_enabled: bool | None = None
    reminder_2h_enabled: bool | None = None
    reminder_channel: Channel | None = None
    default_language: Language | None = None
    confirmation_template_en: str | None = Field(default=None, max_length=1200)
    confirmation_template_hi: str | None = Field(default=None, max_length=1200)
    reminder_24h_template_en: str | None = Field(default=None, max_length=1200)
    reminder_24h_template_hi: str | None = Field(default=None, max_length=1200)
    reminder_2h_template_en: str | None = Field(default=None, max_length=1200)
    reminder_2h_template_hi: str | None = Field(default=None, max_length=1200)


class ConfirmationRequest(BaseModel):
    channel: Channel


class ConfirmationRead(BaseModel):
    ok: bool
    sent: bool
    channel: Channel
    appointment_id: UUID
    reason: str | None = None


class MessageLogRead(ORMModel):
    id: UUID
    clinic_id: UUID
    appointment_id: UUID | None
    channel: str
    kind: str
    recipient: str
    status: str
    provider: str
    provider_message_id: str | None
    error: str
    created_at: datetime
