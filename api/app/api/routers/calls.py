from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...core.time import clinic_timezone
from ...db import SessionDep
from ...models import Call
from ...schemas.calls import CallAnalyticsRead, CallDetailRead
from ...services.call_analytics import build_call_analytics, call_detail
from ...services.common import get_clinic_or_404
from ...services.storage import StorageError, presign_recording_url
from ..deps import CurrentStaff

router = APIRouter(tags=["Calls & Analytics"])


@router.get(
    "/analytics/calls",
    response_model=CallAnalyticsRead,
    summary="Call analytics for the clinic",
    description=(
        "Returns call volume, booking conversion, latency, language split, "
        "cost per minute, transfer rate, and recent calls for a rolling period."
    ),
)
async def call_analytics(
    staff: CurrentStaff,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> CallAnalyticsRead:
    clinic = await get_clinic_or_404(session, staff.clinic_id)
    tz = clinic_timezone(clinic)
    today = datetime.now(UTC).astimezone(tz).date()
    period_start = today - timedelta(days=days - 1)
    start = datetime.combine(period_start, time.min, tzinfo=tz).astimezone(UTC)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)

    calls = list(
        (
            await session.scalars(
                select(Call)
                .where(
                    Call.clinic_id == staff.clinic_id,
                    Call.started_at.is_not(None),
                    Call.started_at >= start,
                    Call.started_at < end,
                )
                .order_by(Call.started_at.desc())
            )
        ).all()
    )
    return build_call_analytics(calls, timezone=tz, days=days, today=today)


@router.get(
    "/calls/{call_id}",
    response_model=CallDetailRead,
    summary="Call detail with transcript and evaluations",
    description="Clinic-scoped call detail. Phone numbers are masked.",
    responses={404: {"description": "Call not found"}},
)
async def get_call(
    call_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> CallDetailRead:
    call = await session.scalar(
        select(Call)
        .options(selectinload(Call.transcripts), selectinload(Call.evaluations))
        .where(Call.id == call_id, Call.clinic_id == staff.clinic_id)
    )
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return call_detail(call)


@router.get(
    "/calls/{call_id}/recording",
    summary="Stream or redirect to a call recording",
    description=(
        "Authenticated recording playback. Redirects to a short-lived S3 URL or "
        "the existing public recording URL."
    ),
    responses={
        404: {"description": "Recording not found"},
        503: {"description": "Recording storage is not configured"},
    },
)
async def get_call_recording(
    call_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> RedirectResponse:
    call = await session.scalar(
        select(Call).where(Call.id == call_id, Call.clinic_id == staff.clinic_id)
    )
    if call is None or not call.recording_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")

    target = call.recording_url
    if target.startswith("s3://"):
        try:
            target = await asyncio.to_thread(presign_recording_url, target)
        except StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    if not target.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    return RedirectResponse(target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
