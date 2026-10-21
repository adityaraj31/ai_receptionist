from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from ...db import SessionDep
from ...models import AvailabilityRule, Call, CallEvent, Doctor, Transcript
from ...queue import enqueue_call_processing
from ...schemas import (
    AgentAvailabilityRead,
    AgentClinicConfigRead,
    AgentClinicRead,
    AgentDoctorRead,
    CallbackCreate,
    CallbackRead,
    CallFinalizeRead,
    CallFinalizeRequest,
    ConfirmationRead,
    ConfirmationRequest,
    FaqSearchRead,
    FaqSearchRequest,
)
from ...services.callbacks import create_callback_task
from ...services.common import get_clinic_or_404
from ...services.faq import find_faq_answer, shorten_answer
from ...services.messaging import send_confirmation
from ..deps import CurrentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.get(
    "/clinic-config",
    response_model=AgentClinicConfigRead,
    summary="Clinic config for the voice agent",
    description=(
        "Service-key endpoint. Returns the clinic, active doctors, and active "
        "availability rules so the voice agent can inject them into its prompt."
    ),
)
async def clinic_config(
    principal: CurrentService,
    session: SessionDep,
) -> AgentClinicConfigRead:
    clinic = await get_clinic_or_404(session, principal.clinic_id)
    doctors = list(
        (
            await session.scalars(
                select(Doctor)
                .where(
                    Doctor.clinic_id == principal.clinic_id,
                    Doctor.is_active.is_(True),
                )
                .order_by(Doctor.name)
            )
        ).all()
    )

    doctor_ids = [doctor.id for doctor in doctors]
    rules = (
        list(
            (
                await session.scalars(
                    select(AvailabilityRule)
                    .where(
                        AvailabilityRule.doctor_id.in_(doctor_ids),
                        AvailabilityRule.is_active.is_(True),
                    )
                    .order_by(
                        AvailabilityRule.weekday,
                        AvailabilityRule.start_time,
                    )
                )
            ).all()
        )
        if doctor_ids
        else []
    )

    return AgentClinicConfigRead(
        clinic=AgentClinicRead(
            id=clinic.id,
            name=clinic.name,
            timezone=clinic.timezone,
            address=clinic.address,
            phone=clinic.phone,
            email=clinic.email,
            front_desk_number=clinic.front_desk_number,
        ),
        doctors=[
            AgentDoctorRead(
                id=doctor.id,
                name=doctor.name,
                specialization=doctor.specialization,
                languages=list(doctor.languages),
                fee=doctor.fee,
            )
            for doctor in doctors
        ],
        availability=[
            AgentAvailabilityRead(
                doctor_id=rule.doctor_id,
                weekday=rule.weekday,
                start_time=rule.start_time,
                end_time=rule.end_time,
                slot_minutes=rule.slot_minutes,
            )
            for rule in rules
        ],
    )


@router.post(
    "/faq/search",
    response_model=FaqSearchRead,
    summary="Search the clinic FAQ knowledge base",
    description=(
        "Service-key endpoint used by the voice agent. Embeds the caller's question "
        "locally, returns the closest active clinic FAQ, and trims the answer to two "
        "short sentences for speech."
    ),
    responses={503: {"description": "FAQ retrieval is temporarily unavailable"}},
)
async def search_faq(
    payload: FaqSearchRequest,
    principal: CurrentService,
    session: SessionDep,
) -> FaqSearchRead:
    started = perf_counter()
    try:
        match = await find_faq_answer(session, principal.clinic_id, payload.query)
    except Exception as exc:
        logger.exception("FAQ search failed for clinic %s", principal.clinic_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FAQ search is temporarily unavailable.",
        ) from exc

    latency_ms = int((perf_counter() - started) * 1000)
    if latency_ms > 300:
        logger.warning(
            "faq_search_slow clinic=%s latency_ms=%s",
            principal.clinic_id,
            latency_ms,
        )
    if match is None:
        return FaqSearchRead(found=False, latency_ms=latency_ms)

    chunk, score = match
    return FaqSearchRead(
        found=True,
        answer=shorten_answer(chunk.answer),
        question=chunk.question,
        score=round(score, 4),
        latency_ms=latency_ms,
    )


@router.post(
    "/callbacks",
    response_model=CallbackRead,
    status_code=201,
    summary="Create a callback task",
    description=(
        "Service-key endpoint used by the voice agent when a human transfer fails "
        "or the caller asks for a callback."
    ),
)
async def create_callback(
    payload: CallbackCreate,
    principal: CurrentService,
    session: SessionDep,
) -> CallbackRead:
    task = await create_callback_task(session, principal.clinic_id, payload)
    return CallbackRead.model_validate(task)


@router.post(
    "/appointments/{appointment_id}/confirmation",
    response_model=ConfirmationRead,
    summary="Send an appointment confirmation",
    description=(
        "Service-key endpoint used by the voice agent after booking. Sends WhatsApp or "
        "SMS using the clinic's enabled settings and language template."
    ),
    responses={404: {"description": "Appointment not found"}},
)
async def send_appointment_confirmation(
    appointment_id: UUID,
    payload: ConfirmationRequest,
    principal: CurrentService,
    session: SessionDep,
) -> ConfirmationRead:
    log = await send_confirmation(
        session,
        principal.clinic_id,
        appointment_id,
        payload.channel,
    )
    sent = log.status == "sent"
    return ConfirmationRead(
        ok=sent,
        sent=sent,
        channel=payload.channel,
        appointment_id=appointment_id,
        reason=None if sent else (log.error or log.status),
    )


@router.post(
    "/calls",
    response_model=CallFinalizeRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Finalize a completed call",
    description=(
        "Service-key endpoint used by the voice agent when a call ends. Stores the "
        "transcript and usage, then enqueues recording storage, summary, cost, and "
        "evaluation jobs. Safe to retry for the same LiveKit room."
    ),
)
async def finalize_call(
    payload: CallFinalizeRequest,
    principal: CurrentService,
    session: SessionDep,
) -> CallFinalizeRead:
    call = await session.scalar(
        select(Call).where(
            Call.clinic_id == principal.clinic_id,
            Call.livekit_room_name == payload.room_name,
        )
    )

    if call is not None and call.post_call_status in {"processing", "completed"}:
        return CallFinalizeRead(
            call_id=call.id,
            queued=False,
            post_call_status=call.post_call_status,
        )

    if call is None:
        call = Call(
            clinic_id=principal.clinic_id,
            livekit_room_name=payload.room_name,
        )
        session.add(call)
        await session.flush()
    else:
        await session.execute(delete(Transcript).where(Transcript.call_id == call.id))

    duration_seconds = max(0, int((payload.ended_at - payload.started_at).total_seconds()))
    call.direction = "inbound"
    call.status = "completed"
    call.from_number = payload.from_number
    call.to_number = payload.to_number
    call.language = payload.language
    call.started_at = payload.started_at
    call.ended_at = payload.ended_at
    call.duration_seconds = duration_seconds
    call.recording_url = payload.recording.url if payload.recording else None
    call.recording_meta = (
        payload.recording.model_dump(exclude_none=True) if payload.recording else {}
    )
    call.usage_metrics = payload.usage.model_dump()
    call.post_call_status = "pending"
    call.post_call_error = ""
    call.evaluation_status = "pending"
    call.evaluation_error = ""

    base_time = datetime.now(UTC)
    session.add_all(
        [
            Transcript(
                call_id=call.id,
                role=turn.role,
                text=turn.text,
                language=turn.language or payload.language,
                created_at=base_time + timedelta(microseconds=index),
            )
            for index, turn in enumerate(payload.transcript)
        ]
    )
    session.add(
        CallEvent(
            call_id=call.id,
            event="call_finalized",
            payload={
                "room_name": payload.room_name,
                "duration_seconds": duration_seconds,
                "turns": len(payload.transcript),
                "has_recording": payload.recording is not None,
                "usage": payload.usage.model_dump(),
            },
        )
    )
    await session.commit()

    queued = await enqueue_call_processing(str(call.id))
    if not queued:
        call.post_call_status = "failed"
        call.post_call_error = "post_call_queue_unavailable"
        session.add(
            CallEvent(
                call_id=call.id,
                event="post_call_enqueue_failed",
                payload={"reason": "post_call_queue_unavailable"},
            )
        )
        await session.commit()

    return CallFinalizeRead(
        call_id=call.id,
        queued=queued,
        post_call_status=call.post_call_status,
    )
