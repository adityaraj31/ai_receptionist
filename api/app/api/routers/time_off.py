from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...db import SessionDep
from ...models import TimeOff
from ...schemas import TimeOffCreate, TimeOffRead, TimeOffUpdate
from ...services.common import get_doctor_or_404
from ..deps import CurrentStaff

router = APIRouter(
    prefix="/doctors/{doctor_id}/time-off",
    tags=["Time Off"],
)


async def _get_time_off_or_404(
    session,
    doctor_id: UUID,
    time_off_id: UUID,
) -> TimeOff:
    entry = await session.scalar(
        select(TimeOff).where(
            TimeOff.id == time_off_id,
            TimeOff.doctor_id == doctor_id,
        )
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time off not found",
        )
    return entry


@router.get(
    "",
    response_model=list[TimeOffRead],
    summary="List doctor time off",
)
async def list_time_off(
    doctor_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> list[TimeOff]:
    await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    entries = await session.scalars(
        select(TimeOff).where(TimeOff.doctor_id == doctor_id).order_by(TimeOff.starts_at)
    )
    return list(entries.all())


@router.post(
    "",
    response_model=TimeOffRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create doctor time off",
    responses={409: {"description": "Overlapping time off"}},
)
async def create_time_off(
    doctor_id: UUID,
    payload: TimeOffCreate,
    staff: CurrentStaff,
    session: SessionDep,
) -> TimeOff:
    doctor = await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    entry = TimeOff(doctor_id=doctor.id, **payload.model_dump())
    session.add(entry)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This time off overlaps an existing entry",
        ) from exc

    await session.refresh(entry)
    return entry


@router.patch(
    "/{time_off_id}",
    response_model=TimeOffRead,
    summary="Update doctor time off",
    responses={
        404: {"description": "Time off not found"},
        409: {"description": "This time off overlaps an existing entry"},
        422: {"description": "Invalid time range"},
    },
)
async def update_time_off(
    doctor_id: UUID,
    time_off_id: UUID,
    payload: TimeOffUpdate,
    staff: CurrentStaff,
    session: SessionDep,
) -> TimeOff:
    await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    entry = await _get_time_off_or_404(session, doctor_id, time_off_id)
    values = payload.model_dump(exclude_unset=True)

    if any(values.get(field) is None for field in ("starts_at", "ends_at") if field in values):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="starts_at and ends_at cannot be null",
        )

    if values.get("reason") is None and "reason" in values:
        values["reason"] = ""

    for field, value in values.items():
        setattr(entry, field, value)

    if entry.ends_at <= entry.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ends_at must be after starts_at",
        )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This time off overlaps an existing entry",
        ) from exc

    await session.refresh(entry)
    return entry


@router.delete(
    "/{time_off_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete doctor time off",
    responses={404: {"description": "Time off not found"}},
)
async def delete_time_off(
    doctor_id: UUID,
    time_off_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> Response:
    await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    entry = await _get_time_off_or_404(session, doctor_id, time_off_id)
    await session.delete(entry)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
