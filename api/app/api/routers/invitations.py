from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ...core.passwords import hash_password
from ...core.security import create_access_token, hash_invitation_token
from ...db import SessionDep
from ...models import Clinic, StaffInvitation, StaffUser
from ...schemas import (
    InvitationAccept,
    InvitationPreview,
    StaffRead,
    TokenResponse,
)
from ...services.common import get_clinic_or_404

router = APIRouter(prefix="/invitations", tags=["Invitations"])


def invalid_invitation() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="This invitation is invalid or has expired.",
    )


@router.get(
    "/{token}",
    response_model=InvitationPreview,
    summary="Preview a staff invitation",
    responses={404: {"description": "Invalid, expired, or used invitation"}},
)
async def preview_invitation(
    token: str,
    session: SessionDep,
) -> InvitationPreview:
    now = datetime.now(UTC)
    result = await session.execute(
        select(StaffInvitation, Clinic)
        .join(Clinic, Clinic.id == StaffInvitation.clinic_id)
        .where(
            StaffInvitation.token_hash == hash_invitation_token(token),
            StaffInvitation.accepted_at.is_(None),
            StaffInvitation.revoked_at.is_(None),
            StaffInvitation.expires_at > now,
            Clinic.is_active.is_(True),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise invalid_invitation()

    invitation, clinic = row
    return InvitationPreview(
        clinic_name=clinic.name,
        email=invitation.email,
        full_name=invitation.full_name,
        role=invitation.role,
        expires_at=invitation.expires_at,
    )


@router.post(
    "/{token}/accept",
    response_model=TokenResponse,
    summary="Accept a staff invitation",
    responses={
        404: {"description": "Invalid, expired, or used invitation"},
        409: {"description": "A staff account already uses this email"},
    },
)
async def accept_invitation(
    token: str,
    payload: InvitationAccept,
    session: SessionDep,
) -> TokenResponse:
    now = datetime.now(UTC)
    invitation = await session.scalar(
        select(StaffInvitation)
        .where(StaffInvitation.token_hash == hash_invitation_token(token))
        .with_for_update()
    )
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= now
    ):
        raise invalid_invitation()

    await get_clinic_or_404(session, invitation.clinic_id)

    existing = await session.scalar(
        select(StaffUser.id).where(func.lower(StaffUser.email) == invitation.email.lower())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A staff account with this email already exists.",
        )

    staff = StaffUser(
        clinic_id=invitation.clinic_id,
        email=invitation.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=invitation.full_name,
        role=invitation.role,
    )
    invitation.accepted_at = now
    session.add(staff)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A staff account with this email already exists.",
        ) from exc

    await session.refresh(staff)
    access_token, expires_in = create_access_token(
        staff.id,
        staff.clinic_id,
        staff.role,
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        staff=StaffRead.model_validate(staff),
    )
