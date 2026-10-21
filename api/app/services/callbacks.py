from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CallbackTask
from ..schemas import CallbackCreate


async def create_callback_task(
    session: AsyncSession,
    clinic_id: UUID,
    payload: CallbackCreate,
    *,
    source: str = "agent",
) -> CallbackTask:
    task = CallbackTask(
        clinic_id=clinic_id,
        caller_name=payload.caller_name,
        phone=payload.phone,
        reason=payload.reason,
        message=payload.message,
        status="pending",
        source=source,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task
