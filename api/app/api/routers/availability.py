from datetime import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...db import SessionDep
from ...models import AvailabilityRule
from ...schemas import (
    AvailabilityRuleCreate,
    AvailabilityRuleRead,
    AvailabilityRuleUpdate,
)
from ...services.common import get_doctor_or_404
from ..deps import CurrentStaff

router = APIRouter(
    prefix="/doctors/{doctor_id}/availability",
    tags=["Availability"],
)


async def _get_rule_or_404(
    session,
    doctor_id: UUID,
    rule_id: UUID,
) -> AvailabilityRule:
    rule = await session.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.id == rule_id,
            AvailabilityRule.doctor_id == doctor_id,
        )
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability rule not found",
        )
    return rule


async def _ensure_no_overlap(
    session,
    doctor_id: UUID,
    weekday: int,
    start_time: time,
    end_time: time,
    *,
    exclude_rule_id: UUID | None = None,
) -> None:
    statement = select(AvailabilityRule).where(
        AvailabilityRule.doctor_id == doctor_id,
        AvailabilityRule.weekday == weekday,
        AvailabilityRule.is_active.is_(True),
    )
    if exclude_rule_id is not None:
        statement = statement.where(AvailabilityRule.id != exclude_rule_id)

    rules = list((await session.scalars(statement)).all())
    for rule in rules:
        if start_time < rule.end_time and end_time > rule.start_time:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This availability window overlaps an existing rule",
            )


@router.get(
    "",
    response_model=list[AvailabilityRuleRead],
    summary="List doctor availability rules",
)
async def list_availability(
    doctor_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
    include_inactive: bool = False,
) -> list[AvailabilityRule]:
    await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    statement = (
        select(AvailabilityRule)
        .where(AvailabilityRule.doctor_id == doctor_id)
        .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
    )
    if not include_inactive:
        statement = statement.where(AvailabilityRule.is_active.is_(True))
    return list((await session.scalars(statement)).all())


@router.post(
    "",
    response_model=AvailabilityRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an availability rule",
    responses={409: {"description": "Overlapping availability rule"}},
)
async def create_availability(
    doctor_id: UUID,
    payload: AvailabilityRuleCreate,
    staff: CurrentStaff,
    session: SessionDep,
) -> AvailabilityRule:
    doctor = await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    if payload.is_active:
        await _ensure_no_overlap(
            session,
            doctor.id,
            payload.weekday,
            payload.start_time,
            payload.end_time,
        )

    rule = AvailabilityRule(doctor_id=doctor.id, **payload.model_dump())
    session.add(rule)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identical availability rule already exists",
        ) from exc

    await session.refresh(rule)
    return rule


@router.patch(
    "/{rule_id}",
    response_model=AvailabilityRuleRead,
    summary="Update an availability rule",
    responses={
        404: {"description": "Availability rule not found"},
        409: {"description": "Overlapping availability rule"},
    },
)
async def update_availability(
    doctor_id: UUID,
    rule_id: UUID,
    payload: AvailabilityRuleUpdate,
    staff: CurrentStaff,
    session: SessionDep,
) -> AvailabilityRule:
    await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    rule = await _get_rule_or_404(session, doctor_id, rule_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    if rule.end_time <= rule.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )
    if rule.is_active:
        await _ensure_no_overlap(
            session,
            doctor_id,
            rule.weekday,
            rule.start_time,
            rule.end_time,
            exclude_rule_id=rule.id,
        )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identical availability rule already exists",
        ) from exc

    await session.refresh(rule)
    return rule


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an availability rule",
    responses={404: {"description": "Availability rule not found"}},
)
async def delete_availability(
    doctor_id: UUID,
    rule_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> Response:
    await get_doctor_or_404(session, doctor_id, staff.clinic_id, include_inactive=True)
    rule = await _get_rule_or_404(session, doctor_id, rule_id)
    await session.delete(rule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
