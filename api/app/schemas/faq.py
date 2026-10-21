from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import ORMModel

QUESTION_MAX = 300
ANSWER_MAX = 4000


def _clean(value: str) -> str:
    return " ".join(value.split())


class FaqCreate(BaseModel):
    question: str = Field(min_length=3, max_length=QUESTION_MAX)
    answer: str = Field(min_length=3, max_length=ANSWER_MAX)
    is_active: bool = True

    @field_validator("question", "answer")
    @classmethod
    def normalize(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class FaqUpdate(BaseModel):
    question: Annotated[str, Field(min_length=3, max_length=QUESTION_MAX)] | None = None
    answer: Annotated[str, Field(min_length=3, max_length=ANSWER_MAX)] | None = None
    is_active: bool | None = None

    @field_validator("question", "answer")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        return _clean(value) if value is not None else None


class FaqRead(ORMModel):
    id: UUID
    question: str
    answer: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FaqSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)

    @field_validator("query")
    @classmethod
    def normalize(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class FaqSearchRead(BaseModel):
    found: bool
    answer: str | None = None
    question: str | None = None
    score: float = 0.0
    latency_ms: int = 0
