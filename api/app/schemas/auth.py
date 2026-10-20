from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class StaffRead(ORMModel):
    id: UUID
    clinic_id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    staff: StaffRead
