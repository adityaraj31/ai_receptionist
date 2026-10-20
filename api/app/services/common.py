from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Appointment, Clinic, Doctor, Patient, StaffUser


async def get_clinic_or_404(session: AsyncSession, clinic_id: UUID) -> Clinic:
    clinic = await session.get(Clinic, clinic_id)
    if clinic is None or not clinic.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found",
        )
    return clinic


async def get_doctor_or_404(
    session: AsyncSession,
    doctor_id: UUID,
    clinic_id: UUID,
    include_inactive: bool = False,
) -> Doctor:
    statement = select(Doctor).where(
        Doctor.id == doctor_id,
        Doctor.clinic_id == clinic_id,
    )
    if not include_inactive:
        statement = statement.where(Doctor.is_active.is_(True))

    doctor = await session.scalar(statement)
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )
    return doctor


async def get_staff_or_404(
    session: AsyncSession,
    staff_id: UUID,
    clinic_id: UUID,
) -> StaffUser:
    staff = await session.scalar(
        select(StaffUser).where(
            StaffUser.id == staff_id,
            StaffUser.clinic_id == clinic_id,
        )
    )
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    return staff


async def get_patient_or_404(
    session: AsyncSession,
    patient_id: UUID,
    clinic_id: UUID,
) -> Patient:
    patient = await session.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


async def get_appointment_or_404(
    session: AsyncSession,
    appointment_id: UUID,
    clinic_id: UUID,
) -> Appointment:
    appointment = await session.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == clinic_id,
        )
    )
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return appointment
