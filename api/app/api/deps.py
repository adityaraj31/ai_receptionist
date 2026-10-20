from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from ..core.security import decode_access_token, hash_service_key
from ..db import SessionDep
from ..models import AgentApiKey, StaffUser

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Staff JWT from POST /api/v1/auth/login",
)
service_key_scheme = APIKeyHeader(
    name="X-Service-Key",
    auto_error=False,
    scheme_name="ServiceKeyAuth",
    description="Service key used by the voice agent",
)


@dataclass(frozen=True)
class Principal:
    clinic_id: UUID
    kind: Literal["staff", "agent"]
    staff_id: UUID | None = None
    role: str | None = None


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _resolve_staff(
    credentials: HTTPAuthorizationCredentials | None,
    session,
) -> StaffUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
        staff_id = UUID(str(payload["sub"]))
        clinic_id = UUID(str(payload["clinic_id"]))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc

    staff = await session.get(StaffUser, staff_id)
    if staff is None or not staff.is_active or staff.clinic_id != clinic_id:
        raise _unauthorized("Staff account is unavailable")
    return staff


async def _resolve_service_key(service_key: str | None, session) -> Principal:
    if not service_key:
        raise _unauthorized("Service key required")

    key_hash = hash_service_key(service_key)
    api_key = await session.scalar(
        select(AgentApiKey).where(
            AgentApiKey.key_hash == key_hash,
            AgentApiKey.is_active.is_(True),
        )
    )
    if api_key is None:
        raise _unauthorized("Invalid service key")

    api_key.last_used_at = datetime.now(UTC)
    await session.commit()
    return Principal(clinic_id=api_key.clinic_id, kind="agent")


async def get_current_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> StaffUser:
    return await _resolve_staff(credentials, session)


async def get_current_admin(staff: CurrentStaff) -> StaffUser:
    if staff.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic admin access required",
        )
    return staff


async def get_service_principal(
    service_key: Annotated[str | None, Depends(service_key_scheme)],
    session: SessionDep,
) -> Principal:
    return await _resolve_service_key(service_key, session)


async def get_any_principal(
    service_key: Annotated[str | None, Depends(service_key_scheme)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> Principal:
    if service_key:
        return await _resolve_service_key(service_key, session)
    if credentials:
        staff = await _resolve_staff(credentials, session)
        return Principal(
            clinic_id=staff.clinic_id,
            kind="staff",
            staff_id=staff.id,
            role=staff.role,
        )
    raise _unauthorized()


CurrentStaff = Annotated[StaffUser, Depends(get_current_staff)]
CurrentAdmin = Annotated[StaffUser, Depends(get_current_admin)]
CurrentService = Annotated[Principal, Depends(get_service_principal)]
AnyPrincipal = Annotated[Principal, Depends(get_any_principal)]
