from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator

from .common import ORMModel, normalize_phone


class ClinicRead(ORMModel):
    id: UUID
    name: str
    timezone: str
    address: str | None
    phone: str | None
    email: str | None
    front_desk_number: str | None
    is_active: bool


class ClinicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    front_desk_number: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Clinic name cannot be blank.")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown timezone.") from exc
        return value

    @field_validator("front_desk_number")
    @classmethod
    def validate_front_desk_number(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_phone(value)
