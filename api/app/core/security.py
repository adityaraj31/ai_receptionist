import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from ..config import settings


def hash_service_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def create_access_token(staff_id: UUID, clinic_id: UUID, role: str) -> tuple[str, int]:
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY is not configured")

    expires_in = settings.access_token_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(staff_id),
        "clinic_id": str(clinic_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "clinic_id", "exp"]},
    )
