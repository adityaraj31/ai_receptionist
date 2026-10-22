from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

CallRole = Literal["user", "assistant"]


class TranscriptTurn(BaseModel):
    role: CallRole
    text: str = Field(min_length=1, max_length=4000)
    language: str | None = Field(default=None, max_length=16)


class RecordingMeta(BaseModel):
    url: str | None = Field(default=None, max_length=2000)
    bucket: str | None = Field(default=None, max_length=255)
    key: str | None = Field(default=None, max_length=1000)
    egress_id: str | None = Field(default=None, max_length=255)
    size_bytes: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)


class CallUsage(BaseModel):
    stt_audio_seconds: float = Field(default=0.0, ge=0)
    llm_prompt_tokens: int = Field(default=0, ge=0)
    llm_completion_tokens: int = Field(default=0, ge=0)
    tts_characters: int = Field(default=0, ge=0)
    average_latency_ms: float | None = Field(default=None, ge=0)
    latency_samples: int = Field(default=0, ge=0)


class CallFinalizeRequest(BaseModel):
    room_name: str = Field(min_length=1, max_length=200)
    started_at: datetime
    ended_at: datetime
    from_number: str | None = Field(default=None, max_length=40)
    to_number: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=16)
    transcript: list[TranscriptTurn] = Field(default_factory=list, max_length=2000)
    recording: RecordingMeta | None = None
    usage: CallUsage = Field(default_factory=CallUsage)

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def check_times(self) -> CallFinalizeRequest:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self


class CallFinalizeRead(BaseModel):
    call_id: UUID
    queued: bool
    post_call_status: str
