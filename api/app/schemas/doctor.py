from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import ORMModel


class DoctorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    specialization: str = ""
    languages: list[str] = Field(default_factory=list)
    fee: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    is_active: bool = True

    @field_validator("languages")
    @classmethod
    def clean_languages(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    specialization: str | None = None
    languages: list[str] | None = None
    fee: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    is_active: bool | None = None

    @field_validator("languages")
    @classmethod
    def clean_languages(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class DoctorRead(ORMModel):
    id: UUID
    clinic_id: UUID
    name: str
    specialization: str
    languages: list[str]
    fee: Decimal
    is_active: bool
