from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from .common import ORMModel

StaffRole = Literal["admin", "staff"]


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: StaffRole | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank.")
        return value


class StaffInvitationCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    role: StaffRole = "staff"

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank.")
        return value


class StaffInvitationRead(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    expires_at: datetime
    created_at: datetime


class StaffInvitationCreated(StaffInvitationRead):
    invite_url: str


class InvitationPreview(BaseModel):
    clinic_name: str
    email: EmailStr
    full_name: str
    role: str
    expires_at: datetime


class InvitationAccept(BaseModel):
    password: str = Field(min_length=12, max_length=128)
