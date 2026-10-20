from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ...core.passwords import verify_password
from ...core.security import create_access_token
from ...db import SessionDep
from ...models import StaffUser
from ...schemas import LoginRequest, StaffRead, TokenResponse
from ..deps import CurrentStaff

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in a staff member",
    responses={401: {"description": "Invalid email or password"}},
)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    staff = await session.scalar(
        select(StaffUser).where(
            func.lower(StaffUser.email) == payload.email.lower(),
            StaffUser.is_active.is_(True),
        )
    )
    if staff is None or not verify_password(payload.password, staff.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token, expires_in = create_access_token(staff.id, staff.clinic_id, staff.role)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        staff=StaffRead.model_validate(staff),
    )


@router.get(
    "/me",
    response_model=StaffRead,
    summary="Get the authenticated staff member",
)
async def me(staff: CurrentStaff) -> StaffRead:
    return StaffRead.model_validate(staff)
