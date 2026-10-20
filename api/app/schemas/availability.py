from datetime import time
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class AvailabilityRuleCreate(BaseModel):
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    slot_minutes: int = Field(default=15, ge=5, le=240)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_window(self) -> "AvailabilityRuleCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityRuleUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    slot_minutes: int | None = Field(default=None, ge=5, le=240)
    is_active: bool | None = None


class AvailabilityRuleRead(ORMModel):
    id: UUID
    doctor_id: UUID
    weekday: int
    start_time: time
    end_time: time
    slot_minutes: int
    is_active: bool
