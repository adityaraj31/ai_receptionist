from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from ..db import SessionLocal
from ..models import Call, CallEvent, Evaluation, Transcript
from ..queue import enqueue_call_evaluation
from .call_analysis import (
    evaluate_transcript,
    format_transcript,
    summarize_call,
)
from .call_costs import compute_call_cost
from .llm import LlmNotConfigured
from .storage import persist_recording

logger = logging.getLogger(__name__)


async def _turns(session, call_id: UUID) -> list[tuple[str, str]]:
    rows = (
        await session.scalars(
            select(Transcript)
            .where(Transcript.call_id == call_id)
            .order_by(Transcript.created_at, Transcript.id)
        )
    ).all()
    return [(row.role, row.text) for row in rows]


async def _mark_failed(call_id: UUID, *, field: str, error: str, event: str) -> None:
    async with SessionLocal() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return
        setattr(call, field, "failed")
        setattr(call, f"{field.replace('_status', '')}_error", error[:1000])
        session.add(CallEvent(call_id=call_id, event=event, payload={"error": error[:500]}))
        await session.commit()


async def process_call(_ctx: dict[str, Any], call_id: str) -> dict[str, str]:
    try:
        identifier = UUID(call_id)
    except ValueError:
        return {"status": "invalid_id"}

    async with SessionLocal() as session:
        call = await session.get(Call, identifier)
        if call is None:
            return {"status": "not_found"}
        if call.post_call_status == "completed":
            if call.evaluation_status in {"pending", "failed"}:
                queued = await enqueue_call_evaluation(str(identifier))
                return {
                    "status": "completed",
                    "evaluation": "queued" if queued else "queue_unavailable",
                }
            return {"status": "completed", "evaluation": call.evaluation_status}

        call.post_call_status = "processing"
        call.post_call_error = ""
        await session.commit()

        try:
            turns = await _turns(session, call.id)
            duration_seconds = call.duration_seconds
            if duration_seconds is None and call.started_at and call.ended_at:
                duration_seconds = max(0, int((call.ended_at - call.started_at).total_seconds()))
                call.duration_seconds = duration_seconds
            duration_seconds = duration_seconds or 0

            recording_url, storage_error = await persist_recording(call, call.recording_meta)
            if recording_url:
                call.recording_url = recording_url
            recording_meta = dict(call.recording_meta or {})
            recording_meta["stored_url"] = recording_url or ""
            recording_meta["storage_error"] = storage_error or ""
            call.recording_meta = recording_meta

            analysis = await summarize_call(turns, duration_seconds)
            cost, cost_breakdown = compute_call_cost(call.usage_metrics, duration_seconds)
            call.summary = analysis.summary
            call.outcome = analysis.outcome
            call.cost = cost
            call.cost_breakdown = cost_breakdown
            call.post_call_status = "completed"
            call.post_call_error = ""
            call.evaluation_status = "pending"
            call.evaluation_error = ""
            session.add(
                CallEvent(
                    call_id=call.id,
                    event="post_call_completed",
                    payload={
                        "source": analysis.source,
                        "analysis_error": analysis.error,
                        "outcome": analysis.outcome,
                        "turns": len(turns),
                        "duration_seconds": duration_seconds,
                        "cost": str(cost),
                        "storage_error": storage_error or "",
                    },
                )
            )
            await session.commit()
            transcript_text = format_transcript(turns)
            logger.info(
                "Post-call processing completed call=%s chars=%s outcome=%s cost=%s",
                call.id,
                len(transcript_text),
                call.outcome,
                call.cost,
            )
        except Exception as exc:
            await session.rollback()
            logger.exception("Post-call processing failed for call %s", identifier)
            await _mark_failed(
                identifier,
                field="post_call_status",
                error=str(exc),
                event="post_call_failed",
            )
            raise

    queued = await enqueue_call_evaluation(str(identifier))
    if not queued:
        await _mark_failed(
            identifier,
            field="evaluation_status",
            error="evaluation_queue_unavailable",
            event="evaluation_enqueue_failed",
        )
        return {"status": "completed", "evaluation": "queue_unavailable"}
    return {"status": "completed", "evaluation": "queued"}


async def evaluate_call(_ctx: dict[str, Any], call_id: str) -> dict[str, str]:
    try:
        identifier = UUID(call_id)
    except ValueError:
        return {"status": "invalid_id"}

    async with SessionLocal() as session:
        call = await session.get(Call, identifier)
        if call is None:
            return {"status": "not_found"}
        if call.evaluation_status == "completed":
            return {"status": "completed"}

        turns = await _turns(session, call.id)
        if not turns:
            call.evaluation_status = "skipped"
            call.evaluation_error = "no_transcript"
            await session.commit()
            return {"status": "skipped", "reason": "no_transcript"}

        call.evaluation_status = "processing"
        call.evaluation_error = ""
        await session.commit()

        try:
            result = await evaluate_transcript(turns, outcome=call.outcome)
        except LlmNotConfigured as exc:
            await session.rollback()
            await _mark_failed(
                identifier,
                field="evaluation_status",
                error=str(exc),
                event="evaluation_failed",
            )
            return {"status": "failed", "reason": "llm_not_configured"}
        except Exception as exc:
            await session.rollback()
            logger.exception("Evaluation failed for call %s", identifier)
            await _mark_failed(
                identifier,
                field="evaluation_status",
                error=str(exc),
                event="evaluation_failed",
            )
            raise

        await session.execute(delete(Evaluation).where(Evaluation.call_id == call.id))
        session.add_all(
            [
                Evaluation(
                    call_id=call.id,
                    metric="correctness",
                    score=Decimal(str(round(result.correctness, 3))),
                    details={"comments": result.comments, "scale": "0-1"},
                ),
                Evaluation(
                    call_id=call.id,
                    metric="politeness",
                    score=Decimal(str(round(result.politeness, 3))),
                    details={"comments": result.comments, "scale": "0-1"},
                ),
                Evaluation(
                    call_id=call.id,
                    metric="missed_handoffs",
                    score=Decimal(len(result.missed_handoffs)),
                    details={
                        "items": result.missed_handoffs,
                        "comments": result.comments,
                        "scale": "count; lower is better",
                    },
                ),
            ]
        )
        call.evaluation_status = "completed"
        call.evaluation_error = ""
        session.add(
            CallEvent(
                call_id=call.id,
                event="evaluation_completed",
                payload={
                    "correctness": result.correctness,
                    "politeness": result.politeness,
                    "missed_handoffs": len(result.missed_handoffs),
                },
            )
        )
        await session.commit()
        return {"status": "completed"}
