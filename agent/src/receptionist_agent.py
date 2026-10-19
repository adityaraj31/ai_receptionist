"""Minimal LiveKit Agents worker for the AI Receptionist.

Pipeline: Silero VAD -> Sarvam STT -> OpenAI-compatible LLM -> Sarvam TTS.
Verified against livekit-agents / livekit-plugins-sarvam 1.8.8.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
    llm,
    metrics,
)
from livekit.plugins import openai, sarvam, silero

AGENT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = AGENT_DIR.parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger("receptionist.latency")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.propagate = False

DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "hi-IN")
TTS_LANGUAGE = os.getenv("SARVAM_LANGUAGE", DEFAULT_LANGUAGE)


def log_event(event: str, **fields: Any) -> None:
    """Write one structured JSON event per line."""
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, separators=(",", ":"), default=str))


def _ms(seconds: float | None) -> float | None:
    return round(seconds * 1000, 1) if seconds is not None else None


def build_instructions(clinic_name: str) -> str:
    return f"""You are the AI phone receptionist for {clinic_name}, a medical clinic in India.

Rules:
- You are an AI. Never claim to be a human.
- Reply in the caller's language: Hindi, English, or Hinglish. Match the language of their
  most recent message.
- Keep every reply to 1-2 short spoken sentences. No lists, markdown, or emojis.
- Never give medical advice, diagnoses, or medicine suggestions. You only help with
  appointments, clinic information, and taking a message.
- Read back critical details to confirm them: patient name, date, time, and phone number.
- If the caller asks for a human, describes a medical emergency, is clearly frustrated, or
  you fail to understand them twice, say a clinic team member will call them back and ask
  for the best number.
- If the caller declines recording consent, acknowledge it and continue helping.
- If you do not know something, say so and offer to have the clinic call back.
"""


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer(setup_fnc=prewarm)


def _on_stt_metrics(m: metrics.STTMetrics) -> None:
    log_event(
        "stt_metrics",
        audio_ms=_ms(m.audio_duration),
        duration_ms=_ms(m.duration),
        streamed=m.streamed,
    )


def _on_llm_metrics(m: metrics.LLMMetrics) -> None:
    log_event(
        "llm_metrics",
        ttft_ms=_ms(m.ttft),
        duration_ms=_ms(m.duration),
        prompt_tokens=m.prompt_tokens,
        completion_tokens=m.completion_tokens,
        tokens_per_second=round(m.tokens_per_second, 2),
        cancelled=m.cancelled,
    )


def _on_tts_metrics(m: metrics.TTSMetrics) -> None:
    log_event(
        "tts_metrics",
        ttfb_ms=_ms(m.ttfb),
        duration_ms=_ms(m.duration),
        audio_ms=_ms(m.audio_duration),
        characters=m.characters_count,
        cancelled=m.cancelled,
    )


def _on_provider_error(stage: str, event: Any) -> None:
    log_event(
        f"{stage}_error",
        label=getattr(event, "label", None),
        recoverable=getattr(event, "recoverable", None),
        error=repr(getattr(event, "error", event)),
    )


def _on_conversation_item(event: ConversationItemAddedEvent) -> None:
    item = event.item
    if not isinstance(item, llm.ChatMessage) or item.role != "assistant":
        return

    m = item.metrics or {}
    if not m:
        return

    log_event(
        "turn_latency",
        e2e_ms=_ms(m.get("e2e_latency")),
        stt_transcription_ms=_ms(m.get("transcription_delay")),
        end_of_turn_ms=_ms(m.get("end_of_turn_delay")),
        llm_ttft_ms=_ms(m.get("llm_node_ttft")),
        llm_first_sentence_ms=_ms(m.get("llm_node_ttfs")),
        tts_ttfb_ms=_ms(m.get("tts_node_ttfb")),
        playback_ms=_ms(m.get("playback_latency")),
        interrupted=item.interrupted,
    )


def _build_session(vad: silero.VAD) -> AgentSession:
    stt = sarvam.STT(
        language=os.getenv("SARVAM_STT_LANGUAGE", "unknown"),
        model=os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
        mode="transcribe",
        sample_rate=16000,
        high_vad_sensitivity=True,
        flush_signal=True,
    )

    llm_kwargs: dict[str, Any] = {
        "model": os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "max_retries": 1,
    }
    if base_url := os.getenv("LLM_BASE_URL"):
        llm_kwargs["base_url"] = base_url
    if temperature := os.getenv("LLM_TEMPERATURE"):
        llm_kwargs["temperature"] = float(temperature)

    tts_kwargs: dict[str, Any] = {
        "target_language_code": TTS_LANGUAGE,
        "model": os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
        "speech_sample_rate": 22050,
    }
    if speaker := os.getenv("SARVAM_TTS_SPEAKER"):
        tts_kwargs["speaker"] = speaker

    session = AgentSession(
        stt=stt,
        vad=vad,
        llm=openai.LLM(**llm_kwargs),
        tts=sarvam.TTS(**tts_kwargs),
        turn_handling=TurnHandlingOptions(
            turn_detection="vad",
            endpointing={"min_delay": 0.3, "max_delay": 3.0},
            interruption={"enabled": True},
        ),
    )

    session.stt.on("metrics_collected", _on_stt_metrics)
    session.llm.on("metrics_collected", _on_llm_metrics)
    session.tts.on("metrics_collected", _on_tts_metrics)
    session.stt.on("error", lambda event: _on_provider_error("stt", event))
    session.llm.on("error", lambda event: _on_provider_error("llm", event))
    session.tts.on("error", lambda event: _on_provider_error("tts", event))
    session.on("conversation_item_added", _on_conversation_item)
    return session


@server.rtc_session(agent_name=os.getenv("LIVEKIT_AGENT_NAME", "ai-receptionist"))
async def receptionist(ctx: JobContext) -> None:
    missing = [name for name in ("SARVAM_API_KEY", "LLM_API_KEY") if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    clinic_name = os.getenv("CLINIC_NAME", "Aarogya Clinic")
    session = _build_session(ctx.proc.userdata["vad"])

    log_event(
        "session_started",
        room=ctx.room.name,
        clinic=clinic_name,
        stt_model=os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        tts_model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
        tts_language=TTS_LANGUAGE,
    )

    await session.start(
        agent=Agent(instructions=build_instructions(clinic_name)),
        room=ctx.room,
    )

    greeting = (
        f"Namaste! Main {clinic_name} ka AI receptionist hoon. "
        "I can help in Hindi or English. This call may be recorded for quality. "
        "Kya aap isse theek hain? How can I help you?"
    )
    session.say(greeting)


def _preflight() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in {"dev", "start", "connect", "console"}:
        return

    required = ["SARVAM_API_KEY", "LLM_API_KEY"]
    if command != "console":
        required = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", *required]

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\n\nFrom the repo root, run:\n"
            + "  cp .env.example .env\n"
            + "Then fill in the LiveKit, Sarvam, and LLM keys in .env."
        )


if __name__ == "__main__":
    _preflight()
    cli.run_app(server)
