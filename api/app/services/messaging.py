from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..messaging import (
    TemplateError,
    build_messaging_service,
    default_templates,
    format_appointment_time,
    render_template,
    validate_template,
)
from ..messaging.base import Channel
from ..models import Appointment, Clinic, ClinicMessagingSettings, MessageLog

ReminderKind = Literal["reminder_24h", "reminder_2h"]


async def get_or_create_messaging_settings(
    session: AsyncSession,
    clinic_id: UUID,
) -> ClinicMessagingSettings:
    settings = await session.get(ClinicMessagingSettings, clinic_id)
    if settings is not None:
        return settings

    settings = ClinicMessagingSettings(clinic_id=clinic_id, **default_templates())
    session.add(settings)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.get(ClinicMessagingSettings, clinic_id)
        if existing is None:
            raise
        return existing
    await session.refresh(settings)
    return settings


async def update_messaging_settings(
    session: AsyncSession,
    clinic_id: UUID,
    values: dict[str, object],
) -> ClinicMessagingSettings:
    settings = await get_or_create_messaging_settings(session, clinic_id)
    for field, value in values.items():
        if field.endswith("_template_en") or field.endswith("_template_hi"):
            try:
                value = validate_template(str(value))
            except TemplateError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
        setattr(settings, field, value)
    await session.commit()
    await session.refresh(settings)
    return settings


async def load_appointment_for_message(
    session: AsyncSession,
    appointment_id: UUID,
    clinic_id: UUID | None = None,
) -> Appointment:
    appointment = await session.scalar(
        select(Appointment)
        .options(
            selectinload(Appointment.clinic),
            selectinload(Appointment.doctor),
            selectinload(Appointment.patient),
        )
        .where(Appointment.id == appointment_id)
    )
    if appointment is None or (clinic_id is not None and appointment.clinic_id != clinic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


def _language(appointment: Appointment, settings: ClinicMessagingSettings) -> str:
    if appointment.language in {"en", "hi"}:
        return appointment.language
    return settings.default_language


def _context(appointment: Appointment, clinic: Clinic) -> dict[str, str]:
    return {
        "patient_name": appointment.patient.name,
        "doctor_name": appointment.doctor.name,
        "clinic_name": clinic.name,
        "clinic_phone": clinic.phone or clinic.front_desk_number or "",
        "appointment_time": format_appointment_time(appointment.starts_at, clinic.timezone),
    }


async def _deliver(
    session: AsyncSession,
    *,
    appointment: Appointment,
    channel: Channel,
    kind: str,
    body: str,
) -> MessageLog:
    result = await build_messaging_service().send(
        channel,
        to=appointment.patient.phone,
        body=body,
    )
    log = MessageLog(
        clinic_id=appointment.clinic_id,
        appointment_id=appointment.id,
        channel=channel,
        kind=kind,
        recipient=appointment.patient.phone,
        status="sent" if result.ok else "failed",
        appointment_starts_at=appointment.starts_at,
        provider=result.provider,
        provider_message_id=result.message_id,
        error=result.error or "",
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def _skip(
    session: AsyncSession,
    *,
    appointment: Appointment,
    channel: Channel,
    kind: str,
    reason: str,
) -> MessageLog:
    log = MessageLog(
        clinic_id=appointment.clinic_id,
        appointment_id=appointment.id,
        channel=channel,
        kind=kind,
        recipient=appointment.patient.phone,
        status="skipped",
        appointment_starts_at=appointment.starts_at,
        provider="",
        error=reason,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def send_confirmation(
    session: AsyncSession,
    clinic_id: UUID,
    appointment_id: UUID,
    channel: Channel,
) -> MessageLog:
    appointment = await load_appointment_for_message(session, appointment_id, clinic_id)
    if appointment.status != "booked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only booked appointments can be confirmed",
        )

    settings = await get_or_create_messaging_settings(session, clinic_id)
    enabled = (
        settings.confirmation_whatsapp_enabled
        if channel == "whatsapp"
        else settings.confirmation_sms_enabled
    )
    if not enabled:
        return await _skip(
            session,
            appointment=appointment,
            channel=channel,
            kind="confirmation",
            reason="confirmation_channel_disabled",
        )

    language = _language(appointment, settings)
    template = getattr(settings, f"confirmation_template_{language}")
    body = render_template(template, _context(appointment, appointment.clinic))
    return await _deliver(
        session,
        appointment=appointment,
        channel=channel,
        kind="confirmation",
        body=body,
    )


async def send_reminder(
    session: AsyncSession,
    appointment: Appointment,
    kind: ReminderKind,
) -> MessageLog:
    settings = await get_or_create_messaging_settings(session, appointment.clinic_id)
    channel: Channel = settings.reminder_channel  # type: ignore[assignment]
    enabled = settings.reminders_enabled and (
        settings.reminder_24h_enabled if kind == "reminder_24h" else settings.reminder_2h_enabled
    )
    if appointment.status != "booked":
        return await _skip(
            session,
            appointment=appointment,
            channel=channel,
            kind=kind,
            reason="appointment_not_booked",
        )
    if not enabled:
        return await _skip(
            session,
            appointment=appointment,
            channel=channel,
            kind=kind,
            reason="reminder_disabled",
        )

    existing = await session.scalar(
        select(MessageLog).where(
            MessageLog.appointment_id == appointment.id,
            MessageLog.kind == kind,
            MessageLog.status == "sent",
            MessageLog.appointment_starts_at == appointment.starts_at,
        )
    )
    if existing is not None:
        return existing

    language = _language(appointment, settings)
    template = getattr(settings, f"{kind}_template_{language}")
    body = render_template(template, _context(appointment, appointment.clinic))
    return await _deliver(
        session,
        appointment=appointment,
        channel=channel,
        kind=kind,
        body=body,
    )
