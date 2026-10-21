from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Call, CallEvent, Evaluation, Transcript
from app.services.call_analysis import CallAnalysis, CallEvaluation
from app.services.post_call import evaluate_call, process_call


def _payload(room_name: str = "room-test-1") -> dict:
    started = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    ended = started + timedelta(minutes=2)
    return {
        "room_name": room_name,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "from_number": "+919000000001",
        "to_number": "+919000000002",
        "language": "hi-IN",
        "transcript": [
            {"role": "user", "text": "Mujhe kal appointment chahiye"},
            {"role": "assistant", "text": "Kal 10 baje slot available hai."},
            {"role": "user", "text": "Book kar dijiye"},
        ],
        "recording": {"url": "s3://recordings/live/room-test-1.ogg", "key": "live/room-test-1.ogg"},
        "usage": {
            "stt_audio_seconds": 120,
            "llm_prompt_tokens": 1000,
            "llm_completion_tokens": 200,
            "tts_characters": 300,
        },
    }


async def _load_call(room_name: str) -> Call:
    async with SessionLocal() as session:
        call = await session.scalar(select(Call).where(Call.livekit_room_name == room_name))
        assert call is not None
        return call


async def test_finalize_call_stores_transcript_and_is_idempotent(
    client, agent_headers, monkeypatch
):
    from app.api.routers import agent as agent_router

    queued: list[str] = []

    async def fake_enqueue(call_id: str) -> bool:
        queued.append(call_id)
        return True

    monkeypatch.setattr(agent_router, "enqueue_call_processing", fake_enqueue)

    payload = _payload()
    response = await client.post("/api/v1/agent/calls", json=payload, headers=agent_headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["queued"] is True
    assert body["post_call_status"] == "pending"
    assert queued == [body["call_id"]]

    call = await _load_call("room-test-1")
    async with SessionLocal() as session:
        transcripts = list(
            (
                await session.scalars(
                    select(Transcript)
                    .where(Transcript.call_id == call.id)
                    .order_by(Transcript.created_at)
                )
            ).all()
        )
        events = list(
            (await session.scalars(select(CallEvent).where(CallEvent.call_id == call.id))).all()
        )
    assert [row.text for row in transcripts] == [
        "Mujhe kal appointment chahiye",
        "Kal 10 baje slot available hai.",
        "Book kar dijiye",
    ]
    assert any(event.event == "call_finalized" for event in events)
    assert call.duration_seconds == 120

    async def fake_summarize(turns, duration_seconds):
        return CallAnalysis(summary="Appointment booked for tomorrow.", outcome="booked")

    async def fake_persist(call, meta):
        return meta.get("url"), None

    async def fake_enqueue_eval(call_id: str) -> bool:
        return True

    from app.services import post_call

    monkeypatch.setattr(post_call, "summarize_call", fake_summarize)
    monkeypatch.setattr(post_call, "persist_recording", fake_persist)
    monkeypatch.setattr(post_call, "enqueue_call_evaluation", fake_enqueue_eval)

    result = await process_call({}, str(call.id))
    assert result["status"] == "completed"

    call = await _load_call("room-test-1")
    assert call.post_call_status == "completed"
    assert call.summary == "Appointment booked for tomorrow."
    assert call.outcome == "booked"
    assert call.cost is not None

    response = await client.post("/api/v1/agent/calls", json=payload, headers=agent_headers)
    assert response.status_code == 202
    assert response.json()["queued"] is False
    assert response.json()["post_call_status"] == "completed"

    async with SessionLocal() as session:
        count = len(
            (await session.scalars(select(Transcript).where(Transcript.call_id == call.id))).all()
        )
    assert count == 3


async def test_process_call_falls_back_when_recording_has_no_storage(
    client, agent_headers, monkeypatch
):
    from app.api.routers import agent as agent_router
    from app.services import post_call

    async def fake_enqueue(call_id: str) -> bool:
        return True

    monkeypatch.setattr(agent_router, "enqueue_call_processing", fake_enqueue)
    response = await client.post(
        "/api/v1/agent/calls", json=_payload("room-no-storage"), headers=agent_headers
    )
    call_id = response.json()["call_id"]

    async def fake_summarize(turns, duration_seconds):
        return CallAnalysis(summary="Caller asked a question.", outcome="enquiry")

    async def fake_persist(call, meta):
        return meta.get("url"), "s3_not_configured"

    async def fake_enqueue_eval(call_id: str) -> bool:
        return True

    monkeypatch.setattr(post_call, "summarize_call", fake_summarize)
    monkeypatch.setattr(post_call, "persist_recording", fake_persist)
    monkeypatch.setattr(post_call, "enqueue_call_evaluation", fake_enqueue_eval)

    assert (await process_call({}, call_id))["status"] == "completed"
    call = await _load_call("room-no-storage")
    assert call.recording_url == "s3://recordings/live/room-test-1.ogg"
    assert call.recording_meta["storage_error"] == "s3_not_configured"


async def test_evaluate_call_writes_metric_rows(client, agent_headers, monkeypatch):
    from app.api.routers import agent as agent_router
    from app.services import post_call

    async def fake_enqueue(call_id: str) -> bool:
        return True

    async def fake_summarize(turns, duration_seconds):
        return CallAnalysis(summary="Transferred to the front desk.", outcome="transferred")

    async def fake_persist(call, meta):
        return meta.get("url"), None

    async def fake_eval(turns, *, outcome):
        assert outcome == "transferred"
        return CallEvaluation(
            correctness=0.9,
            politeness=1.0,
            missed_handoffs=["billing question was not handed off"],
            comments="Agent was polite but missed one handoff.",
        )

    monkeypatch.setattr(agent_router, "enqueue_call_processing", fake_enqueue)
    monkeypatch.setattr(post_call, "summarize_call", fake_summarize)
    monkeypatch.setattr(post_call, "persist_recording", fake_persist)
    monkeypatch.setattr(post_call, "enqueue_call_evaluation", fake_enqueue)
    monkeypatch.setattr(post_call, "evaluate_transcript", fake_eval)

    response = await client.post(
        "/api/v1/agent/calls", json=_payload("room-eval"), headers=agent_headers
    )
    call_id = response.json()["call_id"]
    await process_call({}, call_id)
    assert (await evaluate_call({}, call_id))["status"] == "completed"

    async with SessionLocal() as session:
        call = await session.get(Call, call_id)
        evaluations = list(
            (await session.scalars(select(Evaluation).where(Evaluation.call_id == call.id))).all()
        )
    assert call.evaluation_status == "completed"
    by_metric = {row.metric: row for row in evaluations}
    assert by_metric["correctness"].score == Decimal("0.900")
    assert by_metric["politeness"].score == Decimal("1.000")
    assert by_metric["missed_handoffs"].score == Decimal("1.000")
    assert by_metric["missed_handoffs"].details["items"] == ["billing question was not handed off"]


async def test_evaluate_call_skips_when_transcript_is_empty(client, agent_headers, monkeypatch):
    from app.api.routers import agent as agent_router

    async def fake_enqueue(call_id: str) -> bool:
        return True

    monkeypatch.setattr(agent_router, "enqueue_call_processing", fake_enqueue)
    payload = _payload("room-empty")
    payload["transcript"] = []
    response = await client.post("/api/v1/agent/calls", json=payload, headers=agent_headers)
    call_id = response.json()["call_id"]

    assert (await evaluate_call({}, call_id))["status"] == "skipped"
    call = await _load_call("room-empty")
    assert call.evaluation_status == "skipped"
    assert call.evaluation_error == "no_transcript"
