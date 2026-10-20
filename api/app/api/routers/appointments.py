from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from ...db import SessionDep
from ...schemas import AppointmentCreate, AppointmentRead, AppointmentReschedule
from ...services.appointments import (
    appointment_to_read,
    cancel_appointment,
    create_appointment,
    list_appointments_for_day,
    reschedule_appointment,
)
from ...services.common import get_appointment_or_404
from ..deps import AnyPrincipal, CurrentStaff

router = APIRouter(prefix="/appointments", tags=["Appointments"])

AppointmentStatus = Literal["booked", "cancelled", "completed", "no_show"]


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Book an appointment",
    responses={
        404: {"description": "Doctor or patient not found"},
        409: {"description": "Slot unavailable or already booked"},
    },
)
async def book_appointment(
    payload: AppointmentCreate,
    principal: AnyPrincipal,
    session: SessionDep,
) -> AppointmentRead:
    return await create_appointment(session, principal, payload)


@router.get(
    "",
    response_model=list[AppointmentRead],
    summary="List appointments by day and doctor",
)
async def list_appointments(
    staff: CurrentStaff,
    session: SessionDep,
    day: Annotated[date, Query(alias="date")],
    doctor_id: UUID | None = None,
    status_filter: Annotated[AppointmentStatus | None, Query(alias="status")] = None,
) -> list[AppointmentRead]:
    return await list_appointments_for_day(
        session,
        staff.clinic_id,
        day,
        doctor_id=doctor_id,
        status_filter=status_filter,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentRead,
    summary="Get an appointment",
    responses={404: {"description": "Appointment not found"}},
)
async def get_appointment(
    appointment_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> AppointmentRead:
    appointment = await get_appointment_or_404(session, appointment_id, staff.clinic_id)
    return appointment_to_read(appointment)


@router.patch(
    "/{appointment_id}/reschedule",
    response_model=AppointmentRead,
    summary="Reschedule an appointment",
    responses={
        404: {"description": "Appointment not found"},
        409: {"description": "Appointment cannot be moved to that slot"},
    },
)
async def reschedule(
    appointment_id: UUID,
    payload: AppointmentReschedule,
    principal: AnyPrincipal,
    session: SessionDep,
) -> AppointmentRead:
    return await reschedule_appointment(session, principal, appointment_id, payload)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    summary="Cancel an appointment",
    responses={
        404: {"description": "Appointment not found"},
        409: {"description": "Appointment cannot be cancelled"},
    },
)
async def cancel(
    appointment_id: UUID,
    principal: AnyPrincipal,
    session: SessionDep,
) -> AppointmentRead:
    return await cancel_appointment(session, principal, appointment_id)
