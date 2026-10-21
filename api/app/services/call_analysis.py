from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..config import settings
from .llm import LlmNotConfigured, chat_json

logger = logging.getLogger(__name__)

OUTCOMES = ("booked", "enquiry", "transferred", "dropped")
_ROLE_LABELS = {"user": "Caller", "assistant": "Agent"}

_SUMMARY_SYSTEM = """You summarize phone calls for a clinic receptionist.
Return JSON only with exactly these keys:
{"summary": "two short sentences", "outcome": "booked|enquiry|transferred|dropped"}
Use booked when an appointment was booked or rescheduled, enquiry when the caller only
asked questions, transferred when the call was handed to a human, and dropped when the
call ended before the receptionist could help. Never give medical advice."""

_EVAL_SYSTEM = """You are a QA reviewer for a clinic AI phone receptionist.
Review the transcript for correctness, politeness, and missed handoffs.
Return JSON only with these keys:
{"correctness": 0.0-1.0, "politeness": 0.0-1.0,
 "missed_handoffs": ["short reason", ...], "comments": "one short paragraph"}
A handoff is required for medical emergencies, an explicit request for a human,
billing or insurance questions, repeated frustration, or two failed attempts to understand.
Do not reward medical advice from the agent; the agent must not diagnose or prescribe."""


@dataclass
class CallAnalysis:
    summary: str
    outcome: str
    source: str = "llm"
    error: str = ""


@dataclass
class CallEvaluation:
    correctness: float
    politeness: float
    missed_handoffs: list[str] = field(default_factory=list)
    comments: str = ""


def format_transcript(turns: list[tuple[str, str]]) -> str:
    lines = [
        f"{_ROLE_LABELS.get(role, role)}: {text.strip()}" for role, text in turns if text.strip()
    ]
    text = "\n".join(lines)
    if len(text) > settings.call_transcript_max_chars:
        return text[: settings.call_transcript_max_chars] + "\n[transcript truncated]"
    return text


def fallback_analysis(turns: list[tuple[str, str]]) -> CallAnalysis:
    if not turns:
        return CallAnalysis(
            summary="No conversation was captured for this call.",
            outcome="dropped",
            source="heuristic",
        )

    caller_text = " ".join(text for role, text in turns if role == "user").strip()
    agent_text = " ".join(text for role, text in turns if role == "assistant").strip()
    lower = " ".join(text for _, text in turns).lower()

    if any(term in lower for term in ("transfer", "connect you", "front desk", "human")):
        outcome = "transferred"
    elif any(
        term in lower
        for term in ("confirmed", "booked", "book ho", "appointment is", "appointment has been")
    ):
        outcome = "booked"
    elif len(turns) <= 2:
        outcome = "dropped"
    else:
        outcome = "enquiry"

    summary_bits = []
    if caller_text:
        summary_bits.append(f"Caller: {caller_text[:180]}")
    if agent_text:
        summary_bits.append(f"Agent: {agent_text[:180]}")
    summary = " ".join(summary_bits) or "Call transcript was too short to summarize."
    return CallAnalysis(summary=summary, outcome=outcome, source="heuristic")


def _score(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


async def summarize_call(turns: list[tuple[str, str]], duration_seconds: int) -> CallAnalysis:
    if not turns:
        return fallback_analysis(turns)

    transcript = format_transcript(turns)
    user = f"Call duration: {duration_seconds} seconds.\n\nTranscript:\n{transcript}"
    try:
        payload = await chat_json(_SUMMARY_SYSTEM, user, max_tokens=400)
    except LlmNotConfigured:
        return fallback_analysis(turns)
    except Exception as exc:
        logger.warning("Call summary LLM failed; using fallback", exc_info=True)
        fallback = fallback_analysis(turns)
        fallback.error = str(exc)[:300]
        return fallback

    summary = str(payload.get("summary") or "").strip()
    outcome = str(payload.get("outcome") or "").strip().lower()
    if outcome not in OUTCOMES or not summary:
        fallback = fallback_analysis(turns)
        fallback.error = "LLM returned an invalid summary or outcome"
        return fallback
    return CallAnalysis(summary=summary[:1500], outcome=outcome)


async def evaluate_transcript(
    turns: list[tuple[str, str]],
    *,
    outcome: str | None,
) -> CallEvaluation:
    if not turns:
        raise ValueError("No transcript to evaluate")

    transcript = format_transcript(turns)
    user = f"Recorded outcome: {outcome or 'unknown'}.\n\nTranscript:\n{transcript}"
    payload = await chat_json(_EVAL_SYSTEM, user, max_tokens=600)
    missed = payload.get("missed_handoffs")
    if isinstance(missed, str):
        missed_items = [missed.strip()] if missed.strip() else []
    elif isinstance(missed, list):
        missed_items = [str(item).strip() for item in missed if str(item).strip()]
    else:
        missed_items = []

    return CallEvaluation(
        correctness=_score(payload.get("correctness")),
        politeness=_score(payload.get("politeness")),
        missed_handoffs=missed_items,
        comments=str(payload.get("comments") or "").strip()[:1500],
    )
