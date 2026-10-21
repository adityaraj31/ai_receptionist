from decimal import Decimal

from app.config import settings
from app.services.call_costs import compute_call_cost


def test_compute_call_cost_across_all_providers(monkeypatch):
    monkeypatch.setattr(settings, "stt_cost_per_minute", 2.0)
    monkeypatch.setattr(settings, "llm_input_cost_per_1m_tokens", 1.0)
    monkeypatch.setattr(settings, "llm_output_cost_per_1m_tokens", 2.0)
    monkeypatch.setattr(settings, "tts_cost_per_1m_characters", 3.0)
    monkeypatch.setattr(settings, "telephony_cost_per_minute", 1.0)
    monkeypatch.setattr(settings, "cost_currency", "INR")

    total, breakdown = compute_call_cost(
        {
            "stt_audio_seconds": 60,
            "llm_prompt_tokens": 1_000_000,
            "llm_completion_tokens": 1_000_000,
            "tts_characters": 1_000_000,
        },
        60,
    )

    assert total == Decimal("9.0000")
    assert breakdown["currency"] == "INR"
    assert breakdown["stt"] == "2.0000"
    assert breakdown["llm_input"] == "1.0000"
    assert breakdown["llm_output"] == "2.0000"
    assert breakdown["tts"] == "3.0000"
    assert breakdown["telephony"] == "1.0000"
    assert breakdown["total"] == "9.0000"


def test_compute_call_cost_handles_missing_usage():
    total, breakdown = compute_call_cost(None, None)
    assert total == Decimal("0.0000")
    assert breakdown["total"] == "0.0000"
    assert breakdown["usage"]["duration_seconds"] == 0
