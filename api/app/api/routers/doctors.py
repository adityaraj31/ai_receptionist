from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ...db import SessionDep
from ...models import AvailabilityRule, Doctor
from ...schemas import DoctorCreate, DoctorRead, DoctorUpdate
from ...services.common import get_doctor_or_404
from ..deps import CurrentStaff

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=list[DoctorRead], summary="List clinic doctors")
async def list_doctors(
    staff: CurrentStaff,
    session: SessionDep,
    include_inactive: bool = False,
) -> list[Doctor]:
    statement = select(Doctor).where(Doctor.clinic_id == staff.clinic_id).order_by(Doctor.name)
    if not include_inactive:
        statement = statement.where(Doctor.is_active.is_(True))
    return list((await session.scalars(statement)).all())


@router.post(
    "",
    response_model=DoctorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a doctor",
    responses={409: {"description": "Doctor name already exists in this clinic"}},
)
async def create_doctor(
    payload: DoctorCreate,
    staff: CurrentStaff,
    session: SessionDep,
) -> Doctor:
    doctor = Doctor(clinic_id=staff.clinic_id, **payload.model_dump())
    session.add(doctor)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A doctor with this name already exists in this clinic",
        ) from exc

    await session.refresh(doctor)
    return doctor


@router.get(
    "/{doctor_id}",
    response_model=DoctorRead,
    summary="Get a doctor",
    responses={404: {"description": "Doctor not found"}},
)
async def get_doctor(
    doctor_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> Doctor:
    return await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)


@router.patch(
    "/{doctor_id}",
    response_model=DoctorRead,
    summary="Update a doctor",
    responses={
        404: {"description": "Doctor not found"},
        409: {"description": "Doctor name already exists in this clinic"},
    },
)
async def update_doctor(
    doctor_id: UUID,
    payload: DoctorUpdate,
    staff: CurrentStaff,
    session: SessionDep,
) -> Doctor:
    doctor = await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(doctor, field, value)
    if values.get("is_active") is False:
        await session.execute(
            update(AvailabilityRule)
            .where(AvailabilityRule.doctor_id == doctor.id)
            .values(is_active=False)
        )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A doctor with this name already exists in this clinic",
        ) from exc

    await session.refresh(doctor)
    return doctor


@router.delete(
    "/{doctor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a doctor",
    responses={404: {"description": "Doctor not found"}},
)
async def deactivate_doctor(
    doctor_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> Response:
    doctor = await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    doctor.is_active = False
    await session.execute(
        update(AvailabilityRule)
        .where(AvailabilityRule.doctor_id == doctor.id)
        .values(is_active=False)
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
