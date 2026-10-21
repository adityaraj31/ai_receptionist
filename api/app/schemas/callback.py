from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import ORMModel, normalize_phone

CallbackStatus = Literal["pending", "contacted", "done", "cancelled"]


class CallbackCreate(BaseModel):
    caller_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=7, max_length=40)
    reason: str = Field(default="", max_length=500)
    message: str = Field(default="", max_length=2000)

    @field_validator("caller_name", "reason", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class CallbackUpdate(BaseModel):
    status: CallbackStatus


class CallbackRead(ORMModel):
    id: UUID
    caller_name: str
    phone: str
    reason: str
    message: str
    status: CallbackStatus
    source: str
    created_at: datetime
    updated_at: datetime
