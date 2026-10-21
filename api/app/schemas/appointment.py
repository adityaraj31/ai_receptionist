from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .common import ORMModel


class AppointmentCreate(BaseModel):
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    patient_id: UUID | None = None
    patient_name: str | None = Field(default=None, min_length=1, max_length=200)
    patient_phone: str | None = Field(default=None, min_length=5, max_length=30)
    patient_email: EmailStr | None = None
    notes: str = Field(default="", max_length=1000)
    language: str | None = Field(default=None, pattern="^(en|hi)$")

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_patient_and_time(self) -> "AppointmentCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.patient_id is None and (not self.patient_name or not self.patient_phone):
            raise ValueError("patient_id or patient_name + patient_phone is required")
        if self.patient_id is not None and (self.patient_name or self.patient_phone):
            raise ValueError("use either patient_id or patient_name + patient_phone")
        return self


class AppointmentReschedule(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_time(self) -> "AppointmentReschedule":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class AppointmentRead(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    doctor_name: str
    doctor_specialization: str
    patient_id: UUID
    patient_name: str
    patient_phone: str
    starts_at: datetime
    ends_at: datetime
    status: str
    source: str
    language: str
    notes: str
    fee: Decimal


class PatientRead(ORMModel):
    id: UUID
    clinic_id: UUID
    name: str
    phone: str
    email: str | None
