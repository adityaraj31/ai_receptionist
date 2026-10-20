from fastapi import APIRouter
from sqlalchemy import select

from ...db import SessionDep
from ...models import AvailabilityRule, Doctor
from ...schemas import (
    AgentAvailabilityRead,
    AgentClinicConfigRead,
    AgentClinicRead,
    AgentDoctorRead,
)
from ...services.common import get_clinic_or_404
from ..deps import CurrentService

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
