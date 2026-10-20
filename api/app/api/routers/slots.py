from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from ...db import SessionDep
from ...schemas import FreeSlotRead
from ...services.common import get_clinic_or_404, get_doctor_or_404
from ...services.slots import get_free_slots
from ..deps import AnyPrincipal

router = APIRouter(prefix="/doctors", tags=["Slots"])


@router.get(
    "/{doctor_id}/free-slots",
    response_model=list[FreeSlotRead],
    summary="Get free appointment slots for a doctor and date",
    responses={404: {"description": "Doctor not found"}},
)
async def free_slots(
    doctor_id: UUID,
    principal: AnyPrincipal,
    session: SessionDep,
    day: Annotated[date, Query(alias="date")],
) -> list[FreeSlotRead]:
    clinic = await get_clinic_or_404(session, principal.clinic_id)
    doctor = await get_doctor_or_404(session, doctor_id, principal.clinic_id)
    slots = await get_free_slots(session, clinic, doctor, day)
    return [
        FreeSlotRead(
            doctor_id=slot.doctor_id,
            slot_date=slot.slot_date,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            slot_minutes=slot.slot_minutes,
            timezone=slot.timezone,
        )
        for slot in slots
    ]
