from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CallListItem(BaseModel):
    id: UUID
    started_at: datetime | None
    from_number: str | None
    language: str | None
    duration_seconds: int | None
    outcome: str | None
    cost: float | None
    summary: str | None
    recording_available: bool
    post_call_status: str
    evaluation_status: str


class CallAnalyticsTotals(BaseModel):
    calls: int
    booked: int
    transferred: int
    booking_conversion: float
    transfer_rate: float
    average_latency_ms: float | None
    cost_per_minute: float | None
    total_cost: float
    total_minutes: float
    average_duration_seconds: float | None


class CallAnalyticsDay(BaseModel):
    date: date
    calls: int
    booked: int
    transferred: int


class CallLanguageSplit(BaseModel):
    language: str
    calls: int
    share: float


class CallOutcomeSplit(BaseModel):
    outcome: str
    calls: int
    share: float


class CallAnalyticsRead(BaseModel):
    days: int
    period_start: date
    period_end: date
    totals: CallAnalyticsTotals
    calls_per_day: list[CallAnalyticsDay]
    languages: list[CallLanguageSplit]
    outcomes: list[CallOutcomeSplit]
    recent_calls: list[CallListItem]


class CallTranscriptRead(BaseModel):
    id: UUID
    role: str
    text: str
    language: str | None
    created_at: datetime


class CallEvaluationRead(BaseModel):
    id: UUID
    metric: str
    score: float | None
    details: dict[str, Any]
    created_at: datetime


class CallDetailRead(CallListItem):
    to_number: str | None
    ended_at: datetime | None
    usage_metrics: dict[str, Any]
    cost_breakdown: dict[str, Any]
    post_call_error: str
    evaluation_error: str
    transcript: list[CallTranscriptRead]
    evaluations: list[CallEvaluationRead]
