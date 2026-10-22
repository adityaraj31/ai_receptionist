from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..models import Call
from ..schemas.calls import (
    CallAnalyticsDay,
    CallAnalyticsRead,
    CallAnalyticsTotals,
    CallDetailRead,
    CallEvaluationRead,
    CallLanguageSplit,
    CallListItem,
    CallOutcomeSplit,
    CallTranscriptRead,
)


def mask_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if len(digits) <= 4:
        return f"•••• {digits[-2:]}" if len(digits) >= 2 else "••••"
    prefix = f"+{digits[:2]} " if value.strip().startswith("+") and len(digits) > 8 else ""
    return f"{prefix}••••• ••{digits[-2:]}"


def language_label(value: str | None) -> str:
    if not value:
        return "Unknown"
    normalized = value.strip().lower()
    if not normalized:
        return "Unknown"
    if normalized.startswith(("hi-en", "en-hi", "hinglish")):
        return "Hinglish"
    if normalized.startswith("hi"):
        return "Hindi"
    if normalized.startswith("en"):
        return "English"
    return value.strip()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _latency_ms(call: Call) -> float | None:
    metrics = call.usage_metrics or {}
    for key in ("average_latency_ms", "avg_latency_ms", "e2e_latency_ms"):
        value = _number(metrics.get(key))
        if value is not None:
            return value
    return None


def call_list_item(call: Call) -> CallListItem:
    return CallListItem(
        id=call.id,
        started_at=call.started_at,
        from_number=mask_phone(call.from_number),
        language=call.language,
        duration_seconds=call.duration_seconds,
        outcome=call.outcome,
        cost=float(call.cost) if call.cost is not None else None,
        summary=(call.summary or "")[:280] or None,
        recording_available=bool(call.recording_url),
        post_call_status=call.post_call_status,
        evaluation_status=call.evaluation_status,
    )


def call_detail(call: Call) -> CallDetailRead:
    item = call_list_item(call)
    transcripts = sorted(call.transcripts, key=lambda row: (row.created_at, str(row.id)))
    evaluations = sorted(call.evaluations, key=lambda row: (row.metric, str(row.id)))
    return CallDetailRead(
        **item.model_dump(),
        to_number=mask_phone(call.to_number),
        ended_at=call.ended_at,
        usage_metrics=call.usage_metrics or {},
        cost_breakdown=call.cost_breakdown or {},
        post_call_error=call.post_call_error,
        evaluation_error=call.evaluation_error,
        transcript=[
            CallTranscriptRead(
                id=row.id,
                role=row.role,
                text=row.text,
                language=row.language,
                created_at=row.created_at,
            )
            for row in transcripts
        ],
        evaluations=[
            CallEvaluationRead(
                id=row.id,
                metric=row.metric,
                score=float(row.score) if row.score is not None else None,
                details=row.details or {},
                created_at=row.created_at,
            )
            for row in evaluations
        ],
    )


def build_call_analytics(
    calls: list[Call],
    *,
    timezone: ZoneInfo,
    days: int,
    today: date,
) -> CallAnalyticsRead:
    period_start = today - timedelta(days=days - 1)
    in_period = [
        call
        for call in calls
        if call.started_at is not None
        and period_start <= call.started_at.astimezone(timezone).date() <= today
    ]

    per_day: dict[date, dict[str, int]] = {
        period_start + timedelta(days=index): {
            "calls": 0,
            "booked": 0,
            "transferred": 0,
        }
        for index in range(days)
    }
    language_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    latencies: list[float] = []
    total_cost = 0.0
    total_seconds = 0

    for call in in_period:
        assert call.started_at is not None
        day = call.started_at.astimezone(timezone).date()
        bucket = per_day[day]
        bucket["calls"] += 1

        if call.outcome == "booked":
            bucket["booked"] += 1
        if call.outcome == "transferred":
            bucket["transferred"] += 1

        language_counts[language_label(call.language)] += 1
        outcome_counts[call.outcome or "pending"] += 1

        if call.cost is not None:
            total_cost += float(call.cost)
        if call.duration_seconds:
            total_seconds += call.duration_seconds
        latency = _latency_ms(call)
        if latency is not None:
            latencies.append(latency)

    total_calls = len(in_period)
    booked = sum(1 for call in in_period if call.outcome == "booked")
    transferred = sum(1 for call in in_period if call.outcome == "transferred")
    total_minutes = total_seconds / 60

    totals = CallAnalyticsTotals(
        calls=total_calls,
        booked=booked,
        transferred=transferred,
        booking_conversion=round(booked / total_calls, 4) if total_calls else 0.0,
        transfer_rate=round(transferred / total_calls, 4) if total_calls else 0.0,
        average_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else None,
        cost_per_minute=round(total_cost / total_minutes, 4) if total_minutes else None,
        total_cost=round(total_cost, 4),
        total_minutes=round(total_minutes, 2),
        average_duration_seconds=(round(total_seconds / total_calls, 1) if total_calls else None),
    )

    recent = sorted(
        in_period,
        key=lambda call: call.started_at or call.created_at,
        reverse=True,
    )[:10]

    return CallAnalyticsRead(
        days=days,
        period_start=period_start,
        period_end=today,
        totals=totals,
        calls_per_day=[
            CallAnalyticsDay(date=day, **counts) for day, counts in sorted(per_day.items())
        ],
        languages=[
            CallLanguageSplit(
                language=language,
                calls=count,
                share=round(count / total_calls, 4) if total_calls else 0.0,
            )
            for language, count in sorted(
                language_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        outcomes=[
            CallOutcomeSplit(
                outcome=outcome,
                calls=count,
                share=round(count / total_calls, 4) if total_calls else 0.0,
            )
            for outcome, count in sorted(
                outcome_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        recent_calls=[call_list_item(call) for call in recent],
    )
