from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from ...config import settings
from ...core.security import hash_invitation_token
from ...db import SessionDep
from ...models import StaffInvitation, StaffUser
from ...schemas import (
    StaffInvitationCreate,
    StaffInvitationCreated,
    StaffInvitationRead,
    StaffRead,
    StaffUpdate,
)
from ...services.common import get_staff_or_404
from ..deps import CurrentAdmin

router = APIRouter(prefix="/staff", tags=["Staff"])

INVITATION_TTL = timedelta(days=7)


def invitation_url(token: str) -> str:
    return f"{settings.dashboard_url.rstrip('/')}/accept-invite/{token}"


@router.get(
    "",
    response_model=list[StaffRead],
    summary="List staff in the clinic",
)
async def list_staff(admin: CurrentAdmin, session: SessionDep) -> list[StaffRead]:
    staff = await session.scalars(
        select(StaffUser)
        .where(StaffUser.clinic_id == admin.clinic_id)
        .order_by(StaffUser.created_at)
    )
    return [StaffRead.model_validate(member) for member in staff]


@router.post(
    "/invitations",
    response_model=StaffInvitationCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a staff member",
    responses={409: {"description": "Email already exists or invitation is pending"}},
)
async def create_invitation(
    payload: StaffInvitationCreate,
    admin: CurrentAdmin,
    session: SessionDep,
) -> StaffInvitationCreated:
    email = payload.email.lower()
    now = datetime.now(UTC)

    existing_staff = await session.scalar(
        select(StaffUser.id).where(func.lower(StaffUser.email) == email)
    )
    if existing_staff is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A staff account with this email already exists.",
        )

    pending = await session.scalar(
        select(StaffInvitation.id).where(
            StaffInvitation.clinic_id == admin.clinic_id,
            func.lower(StaffInvitation.email) == email,
            StaffInvitation.accepted_at.is_(None),
            StaffInvitation.revoked_at.is_(None),
            StaffInvitation.expires_at > now,
        )
    )
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invitation is already pending for this email.",
        )

    token = secrets.token_urlsafe(32)
    invitation = StaffInvitation(
        clinic_id=admin.clinic_id,
        email=email,
        full_name=payload.full_name,
        role=payload.role,
        token_hash=hash_invitation_token(token),
        expires_at=now + INVITATION_TTL,
        invited_by_staff_id=admin.id,
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)

    base = StaffInvitationRead.model_validate(invitation)
    return StaffInvitationCreated(
        **base.model_dump(),
        invite_url=invitation_url(token),
    )


@router.get(
    "/invitations",
    response_model=list[StaffInvitationRead],
    summary="List pending staff invitations",
)
async def list_invitations(
    admin: CurrentAdmin,
    session: SessionDep,
) -> list[StaffInvitationRead]:
    now = datetime.now(UTC)
    invitations = await session.scalars(
        select(StaffInvitation)
        .where(
            StaffInvitation.clinic_id == admin.clinic_id,
            StaffInvitation.accepted_at.is_(None),
            StaffInvitation.revoked_at.is_(None),
            StaffInvitation.expires_at > now,
        )
        .order_by(StaffInvitation.created_at.desc())
    )
    return [StaffInvitationRead.model_validate(item) for item in invitations]


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a pending staff invitation",
    responses={409: {"description": "Invitation has already been accepted"}},
)
async def revoke_invitation(
    invitation_id: UUID,
    admin: CurrentAdmin,
    session: SessionDep,
) -> Response:
    invitation = await session.scalar(
        select(StaffInvitation).where(
            StaffInvitation.id == invitation_id,
            StaffInvitation.clinic_id == admin.clinic_id,
        )
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invitation has already been accepted.",
        )

    invitation.revoked_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{staff_id}",
    response_model=StaffRead,
    summary="Update a staff member",
    responses={409: {"description": "The clinic would lose its last admin"}},
)
async def update_staff(
    staff_id: UUID,
    payload: StaffUpdate,
    admin: CurrentAdmin,
    session: SessionDep,
) -> StaffRead:
    member = await get_staff_or_404(session, staff_id, admin.clinic_id)
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)

    if member.id == admin.id and (
        updates.get("is_active") is False
        or (updates.get("role") is not None and updates["role"] != "admin")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin access.",
        )

    losing_admin = (
        member.role == "admin"
        and member.is_active
        and (
            updates.get("is_active") is False
            or (updates.get("role") is not None and updates["role"] != "admin")
        )
    )
    if losing_admin:
        other_admins = await session.scalar(
            select(func.count())
            .select_from(StaffUser)
            .where(
                StaffUser.clinic_id == admin.clinic_id,
                StaffUser.role == "admin",
                StaffUser.is_active.is_(True),
                StaffUser.id != member.id,
            )
        )
        if not other_admins:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The clinic must keep at least one active admin.",
            )

    for field, value in updates.items():
        setattr(member, field, value)
    await session.commit()
    await session.refresh(member)
    return StaffRead.model_validate(member)
