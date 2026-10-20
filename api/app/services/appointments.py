from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import Principal
from ..core.time import clinic_timezone, day_bounds, to_utc
from ..models import Appointment, Clinic, Doctor, Patient
from ..schemas import AppointmentCreate, AppointmentRead, AppointmentReschedule
from .common import (
    get_appointment_or_404,
    get_clinic_or_404,
    get_doctor_or_404,
    get_patient_or_404,
)
from .slots import get_free_slots


def appointment_to_read(
    appointment: Appointment,
    doctor: Doctor | None = None,
    patient: Patient | None = None,
) -> AppointmentRead:
    doctor = doctor or appointment.doctor
    patient = patient or appointment.patient
    return AppointmentRead(
        id=appointment.id,
        clinic_id=appointment.clinic_id,
        doctor_id=appointment.doctor_id,
        doctor_name=doctor.name,
        doctor_specialization=doctor.specialization,
        patient_id=appointment.patient_id,
        patient_name=patient.name,
        patient_phone=patient.phone,
        starts_at=appointment.starts_at,
        ends_at=appointment.ends_at,
        status=appointment.status,
        source=appointment.source,
        notes=appointment.notes,
        fee=doctor.fee,
    )


async def resolve_patient(
    session: AsyncSession,
    clinic_id: UUID,
    *,
    patient_id: UUID | None,
    patient_name: str | None,
    patient_phone: str | None,
    patient_email: str | None,
) -> Patient:
    if patient_id is not None:
        return await get_patient_or_404(session, patient_id, clinic_id)

    if patient_name is None or patient_phone is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="patient_name and patient_phone are required",
        )

    statement = (
        pg_insert(Patient)
        .values(
            clinic_id=clinic_id,
            name=patient_name,
            phone=patient_phone,
            email=patient_email,
        )
        .on_conflict_do_nothing(index_elements=[Patient.clinic_id, Patient.phone])
        .returning(Patient.id)
    )
    resolved_id = await session.scalar(statement)
    if resolved_id is None:
        resolved_id = await session.scalar(
            select(Patient.id).where(
                Patient.clinic_id == clinic_id,
                Patient.phone == patient_phone,
            )
        )
    if resolved_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not resolve patient",
        )

    patient = await session.get(Patient, resolved_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not resolve patient",
        )
    return patient


async def ensure_slot_is_free(
    session: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    starts_at: datetime,
    ends_at: datetime,
    *,
    exclude_appointment_id: UUID | None = None,
) -> None:
    local_day = starts_at.astimezone(clinic_timezone(clinic)).date()
    slots = await get_free_slots(
        session,
        clinic,
        doctor,
        local_day,
        exclude_appointment_id=exclude_appointment_id,
    )
    wanted_start = to_utc(starts_at)
    wanted_end = to_utc(ends_at)

    for slot in slots:
        if to_utc(slot.starts_at) == wanted_start and to_utc(slot.ends_at) == wanted_end:
            return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Selected slot is not available",
    )


async def create_appointment(
    session: AsyncSession,
    principal: Principal,
    payload: AppointmentCreate,
) -> AppointmentRead:
    clinic = await get_clinic_or_404(session, principal.clinic_id)
    doctor = await get_doctor_or_404(session, payload.doctor_id, principal.clinic_id)
    await ensure_slot_is_free(
        session,
        clinic,
        doctor,
        payload.starts_at,
        payload.ends_at,
    )
    patient = await resolve_patient(
        session,
        principal.clinic_id,
        patient_id=payload.patient_id,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        patient_email=payload.patient_email,
    )

    appointment = Appointment(
        clinic_id=principal.clinic_id,
        doctor_id=doctor.id,
        patient_id=patient.id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        status="booked",
        source=principal.kind,
        notes=payload.notes,
        created_by_staff_id=principal.staff_id,
    )
    session.add(appointment)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot was just booked. Choose another slot.",
        ) from exc

    return appointment_to_read(appointment, doctor, patient)


async def reschedule_appointment(
    session: AsyncSession,
    principal: Principal,
    appointment_id: UUID,
    payload: AppointmentReschedule,
) -> AppointmentRead:
    appointment = await get_appointment_or_404(session, appointment_id, principal.clinic_id)
    if appointment.status != "booked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only booked appointments can be rescheduled",
        )

    clinic = await get_clinic_or_404(session, principal.clinic_id)
    doctor = await get_doctor_or_404(session, appointment.doctor_id, principal.clinic_id)
    await ensure_slot_is_free(
        session,
        clinic,
        doctor,
        payload.starts_at,
        payload.ends_at,
        exclude_appointment_id=appointment.id,
    )

    appointment.starts_at = payload.starts_at
    appointment.ends_at = payload.ends_at

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot was just booked. Choose another slot.",
        ) from exc

    return appointment_to_read(appointment, doctor)


async def cancel_appointment(
    session: AsyncSession,
    principal: Principal,
    appointment_id: UUID,
) -> AppointmentRead:
    appointment = await get_appointment_or_404(session, appointment_id, principal.clinic_id)
    if appointment.status == "cancelled":
        return appointment_to_read(appointment)
    if appointment.status != "booked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only booked appointments can be cancelled",
        )

    appointment.status = "cancelled"
    await session.commit()
    return appointment_to_read(appointment)


async def list_appointments_for_day(
    session: AsyncSession,
    clinic_id: UUID,
    day: date,
    *,
    doctor_id: UUID | None = None,
    status_filter: str | None = None,
) -> list[AppointmentRead]:
    clinic = await get_clinic_or_404(session, clinic_id)
    day_start, day_end = day_bounds(day, clinic_timezone(clinic))

    statement = (
        select(Appointment)
        .where(
            Appointment.clinic_id == clinic_id,
            Appointment.starts_at >= day_start,
            Appointment.starts_at < day_end,
        )
        .order_by(Appointment.starts_at)
    )
    if doctor_id is not None:
        statement = statement.where(Appointment.doctor_id == doctor_id)
    if status_filter is not None:
        statement = statement.where(Appointment.status == status_filter)

    appointments = list((await session.scalars(statement)).all())
    return [appointment_to_read(appointment) for appointment in appointments]
