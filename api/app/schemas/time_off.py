from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import ORMModel


class TimeOffCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(default="", max_length=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "TimeOffCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class TimeOffRead(ORMModel):
    id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str
