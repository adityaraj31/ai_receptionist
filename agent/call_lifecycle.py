"""Collect a call transcript/usage and submit it to the API at shutdown."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from api_client import AgentApiClient
from recording import RecordingSession

logger = logging.getLogger("receptionist.lifecycle")


@dataclass
class UsageCollector:
    stt_audio_seconds: float = 0.0
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    tts_characters: int = 0

    def on_stt_metrics(self, metrics: Any) -> None:
        self.stt_audio_seconds += float(getattr(metrics, "audio_duration", 0) or 0)

    def on_llm_metrics(self, metrics: Any) -> None:
        self.llm_prompt_tokens += int(getattr(metrics, "prompt_tokens", 0) or 0)
        self.llm_completion_tokens += int(getattr(metrics, "completion_tokens", 0) or 0)

    def on_tts_metrics(self, metrics: Any) -> None:
        self.tts_characters += int(getattr(metrics, "characters_count", 0) or 0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stt_audio_seconds": round(self.stt_audio_seconds, 3),
            "llm_prompt_tokens": self.llm_prompt_tokens,
            "llm_completion_tokens": self.llm_completion_tokens,
            "tts_characters": self.tts_characters,
        }


@dataclass
class CallLifecycle:
    api: AgentApiClient
    room_name: str
    started_at: datetime
    from_number: str | None
    to_number: str | None
    language: str | None
    on_event: Callable[..., None]
    recording: RecordingSession
    usage: UsageCollector = field(default_factory=UsageCollector)
    transcript: list[dict[str, str]] = field(default_factory=list)
    _shutdown_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _shutdown_done: bool = field(default=False, init=False)

    def on_conversation_item(self, event: Any) -> None:
        item = getattr(event, "item", None)
        role = getattr(item, "role", None)
        if role not in {"user", "assistant"} or len(self.transcript) >= 2000:
            return
        text = str(getattr(item, "text_content", "") or "").strip()
        if not text:
            return
        self.transcript.append(
            {
                "role": role,
                "text": text[:4000],
                "language": self.language,
            }
        )

    def _payload(self, recording: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "room_name": self.room_name,
            "started_at": self.started_at.isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "from_number": self.from_number,
            "to_number": self.to_number,
            "language": self.language,
            "transcript": self.transcript,
            "recording": recording,
            "usage": self.usage.as_dict(),
        }

    async def shutdown(self) -> None:
        async with self._shutdown_lock:
            if self._shutdown_done:
                return
            self._shutdown_done = True
            try:
                recorded = await self.recording.stop()
            except Exception as exc:
                self.on_event("recording_shutdown_error", error=repr(exc))
                recorded = None
            finally:
                await self.recording.close()

            payload = self._payload(recorded)
            if not self.api.api_key:
                self.on_event("call_finalize_skipped", reason="missing_api_key")
                await self.api.aclose()
                return

            for attempt in range(2):
                try:
                    result = await self.api.finalize_call(payload)
                    self.on_event(
                        "call_finalized",
                        call_id=(result or {}).get("call_id"),
                        queued=(result or {}).get("queued"),
                        turns=len(self.transcript),
                        recording=bool(recorded),
                    )
                    break
                except Exception as exc:
                    self.on_event(
                        "call_finalize_error",
                        attempt=attempt + 1,
                        error=repr(exc),
                    )
                    if attempt == 0:
                        await asyncio.sleep(0.5)
            await self.api.aclose()
