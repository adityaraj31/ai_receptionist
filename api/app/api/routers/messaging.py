from fastapi import APIRouter

from ...db import SessionDep
from ...schemas import MessagingSettingsRead, MessagingSettingsUpdate
from ...services.messaging import (
    get_or_create_messaging_settings,
    update_messaging_settings,
)
from ..deps import CurrentStaff

router = APIRouter(prefix="/messaging-settings", tags=["Messaging"])


@router.get(
    "",
    response_model=MessagingSettingsRead,
    summary="Get clinic messaging settings and templates",
)
async def get_settings(staff: CurrentStaff, session: SessionDep) -> MessagingSettingsRead:
    settings = await get_or_create_messaging_settings(session, staff.clinic_id)
    return MessagingSettingsRead.model_validate(settings)


@router.patch(
    "",
    response_model=MessagingSettingsRead,
    summary="Update clinic messaging settings and templates",
)
async def update_settings(
    payload: MessagingSettingsUpdate,
    staff: CurrentStaff,
    session: SessionDep,
) -> MessagingSettingsRead:
    settings = await update_messaging_settings(
        session,
        staff.clinic_id,
        payload.model_dump(exclude_unset=True, exclude_none=True),
    )
    return MessagingSettingsRead.model_validate(settings)
