from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from ...db import SessionDep
from ...models import CallbackTask
from ...schemas import CallbackRead, CallbackStatus, CallbackUpdate
from ..deps import CurrentStaff

router = APIRouter(prefix="/callbacks", tags=["Callbacks"])


@router.get(
    "",
    response_model=list[CallbackRead],
    summary="List callback tasks for the clinic",
)
async def list_callbacks(
    staff: CurrentStaff,
    session: SessionDep,
    status_filter: Annotated[CallbackStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CallbackTask]:
    query = select(CallbackTask).where(CallbackTask.clinic_id == staff.clinic_id)
    if status_filter:
        query = query.where(CallbackTask.status == status_filter)
    query = query.order_by(CallbackTask.created_at.desc()).limit(limit)
    return list((await session.scalars(query)).all())


@router.patch(
    "/{callback_id}",
    response_model=CallbackRead,
    summary="Update a callback task status",
)
async def update_callback(
    callback_id: UUID,
    payload: CallbackUpdate,
    staff: CurrentStaff,
    session: SessionDep,
) -> CallbackTask:
    task = await session.scalar(
        select(CallbackTask).where(
            CallbackTask.id == callback_id,
            CallbackTask.clinic_id == staff.clinic_id,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Callback task not found.",
        )
    task.status = payload.status
    await session.commit()
    await session.refresh(task)
    return task
