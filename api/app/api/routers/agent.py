from __future__ import annotations

import logging
from time import perf_counter

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ...db import SessionDep
from ...models import AvailabilityRule, Doctor
from ...schemas import (
    AgentAvailabilityRead,
    AgentClinicConfigRead,
    AgentClinicRead,
    AgentDoctorRead,
    CallbackCreate,
    CallbackRead,
    FaqSearchRead,
    FaqSearchRequest,
)
from ...services.callbacks import create_callback_task
from ...services.common import get_clinic_or_404
from ...services.faq import find_faq_answer, shorten_answer
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
