from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ..config import settings

_MONEY = Decimal("0.0001")
_MILLION = Decimal("1000000")
_SIXTY = Decimal("60")


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (ValueError, TypeError):
        return Decimal("0")


def compute_call_cost(
    usage: dict[str, Any] | None,
    duration_seconds: int | float | None,
) -> tuple[Decimal, dict[str, Any]]:
    usage = usage or {}
    stt_seconds = _decimal(usage.get("stt_audio_seconds"))
    prompt_tokens = _decimal(usage.get("llm_prompt_tokens"))
    completion_tokens = _decimal(usage.get("llm_completion_tokens"))
    tts_characters = _decimal(usage.get("tts_characters"))
    duration = _decimal(duration_seconds)

    stt = (stt_seconds / _SIXTY) * _decimal(settings.stt_cost_per_minute)
    llm_input = (prompt_tokens / _MILLION) * _decimal(settings.llm_input_cost_per_1m_tokens)
    llm_output = (completion_tokens / _MILLION) * _decimal(settings.llm_output_cost_per_1m_tokens)
    tts = (tts_characters / _MILLION) * _decimal(settings.tts_cost_per_1m_characters)
    telephony = (duration / _SIXTY) * _decimal(settings.telephony_cost_per_minute)

    total = (stt + llm_input + llm_output + tts + telephony).quantize(
        _MONEY, rounding=ROUND_HALF_UP
    )
    breakdown = {
        "currency": settings.cost_currency,
        "stt": str(stt.quantize(_MONEY, rounding=ROUND_HALF_UP)),
        "llm_input": str(llm_input.quantize(_MONEY, rounding=ROUND_HALF_UP)),
        "llm_output": str(llm_output.quantize(_MONEY, rounding=ROUND_HALF_UP)),
        "tts": str(tts.quantize(_MONEY, rounding=ROUND_HALF_UP)),
        "telephony": str(telephony.quantize(_MONEY, rounding=ROUND_HALF_UP)),
        "total": str(total),
        "usage": {
            "stt_audio_seconds": str(stt_seconds),
            "llm_prompt_tokens": int(prompt_tokens),
            "llm_completion_tokens": int(completion_tokens),
            "tts_characters": int(tts_characters),
            "duration_seconds": int(duration),
        },
        "rates": {
            "stt_per_minute": settings.stt_cost_per_minute,
            "llm_input_per_1m_tokens": settings.llm_input_cost_per_1m_tokens,
            "llm_output_per_1m_tokens": settings.llm_output_cost_per_1m_tokens,
            "tts_per_1m_characters": settings.tts_cost_per_1m_characters,
            "telephony_per_minute": settings.telephony_cost_per_minute,
        },
    }
    return total, breakdown
