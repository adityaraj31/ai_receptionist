from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models import Call, Clinic, Evaluation, Transcript

KOLKATA = ZoneInfo("Asia/Kolkata")


def _call(
    clinic_id,
    *,
    started_at: datetime,
    outcome: str | None,
    language: str | None,
    cost: str,
    duration_seconds: int,
    latency_ms: float | None = None,
    phone: str = "+919000000001",
    recording_url: str | None = None,
) -> Call:
    usage = {}
    if latency_ms is not None:
        usage = {"average_latency_ms": latency_ms, "latency_samples": 3}
    call = Call(
        clinic_id=clinic_id,
        from_number=phone,
        to_number="+919000000099",
        language=language,
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=duration_seconds),
        duration_seconds=duration_seconds,
        outcome=outcome,
        cost=Decimal(cost),
        usage_metrics=usage,
        recording_url=recording_url,
        post_call_status="completed",
        evaluation_status="completed",
    )
    return call


async def _seed_calls(db_session, clinic):
    today = datetime.now(UTC).astimezone(KOLKATA).date()
    base = datetime.combine(today, time(10, 0), tzinfo=KOLKATA)
    yesterday = base - timedelta(days=1)

    booked = _call(
        clinic.id,
        started_at=base,
        outcome="booked",
        language="hi-IN",
        cost="1.0000",
        duration_seconds=60,
        latency_ms=800,
    )
    enquiry = _call(
        clinic.id,
        started_at=base + timedelta(minutes=30),
        outcome="enquiry",
        language="en-IN",
        cost="2.0000",
        duration_seconds=120,
        latency_ms=1000,
    )
    transferred = _call(
        clinic.id,
        started_at=base + timedelta(minutes=60),
        outcome="transferred",
        language="hi-IN",
        cost="3.0000",
        duration_seconds=180,
        phone="+919000000123",
        recording_url="https://recordings.example.com/call.ogg",
    )
    dropped = _call(
        clinic.id,
        started_at=yesterday,
        outcome=None,
        language=None,
        cost="4.0000",
        duration_seconds=240,
        latency_ms=1200,
    )
    db_session.add_all([booked, enquiry, transferred, dropped])
    await db_session.commit()
    for row in (booked, enquiry, transferred, dropped):
        await db_session.refresh(row)

    transcript_time = datetime.now(UTC)
    db_session.add_all(
        [
            Transcript(
                call_id=booked.id,
                role="user",
                text="Kal appointment chahiye",
                created_at=transcript_time,
            ),
            Transcript(
                call_id=booked.id,
                role="assistant",
                text="Book kar diya.",
                created_at=transcript_time + timedelta(microseconds=1),
            ),
            Evaluation(
                call_id=booked.id,
                metric="correctness",
                score=Decimal("0.900"),
                details={"comments": "Good"},
            ),
            Evaluation(
                call_id=booked.id,
                metric="politeness",
                score=Decimal("1.000"),
                details={"comments": "Polite"},
            ),
            Evaluation(
                call_id=booked.id,
                metric="missed_handoffs",
                score=Decimal("0.000"),
                details={"items": []},
            ),
        ]
    )
    await db_session.commit()
    return booked, transferred


async def test_call_analytics_aggregates_metrics(client, db_session, clinic, auth_headers):
    await _seed_calls(db_session, clinic)

    response = await client.get("/api/v1/analytics/calls?days=7", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    totals = body["totals"]
    assert totals["calls"] == 4
    assert totals["booked"] == 1
    assert totals["transferred"] == 1
    assert totals["booking_conversion"] == 0.25
    assert totals["transfer_rate"] == 0.25
    assert totals["average_latency_ms"] == 1000.0
    assert totals["total_cost"] == 10.0
    assert totals["total_minutes"] == 10.0
    assert totals["cost_per_minute"] == 1.0

    assert len(body["calls_per_day"]) == 7
    assert sum(day["calls"] for day in body["calls_per_day"]) == 4
    assert body["languages"] == [
        {"language": "Hindi", "calls": 2, "share": 0.5},
        {"language": "English", "calls": 1, "share": 0.25},
        {"language": "Unknown", "calls": 1, "share": 0.25},
    ]
    assert len(body["recent_calls"]) == 4
    assert body["recent_calls"][0]["from_number"] == "+91 ••••• ••23"
    assert body["recent_calls"][0]["recording_available"] is True


async def test_call_analytics_is_clinic_scoped_and_requires_auth(
    client, db_session, clinic, auth_headers
):
    await _seed_calls(db_session, clinic)
    other = Clinic(name="Other Clinic", timezone="Asia/Kolkata")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    db_session.add(
        _call(
            other.id,
            started_at=datetime.now(UTC),
            outcome="booked",
            language="en-IN",
            cost="9.0000",
            duration_seconds=60,
        )
    )
    await db_session.commit()

    anonymous = await client.get("/api/v1/analytics/calls")
    assert anonymous.status_code == 401

    response = await client.get("/api/v1/analytics/calls?days=7", headers=auth_headers)
    assert response.json()["totals"]["calls"] == 4


async def test_call_detail_includes_transcript_and_scores(client, db_session, clinic, auth_headers):
    booked, _ = await _seed_calls(db_session, clinic)

    response = await client.get(f"/api/v1/calls/{booked.id}", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["summary"] is None
    assert [turn["role"] for turn in body["transcript"]] == ["user", "assistant"]
    assert body["transcript"][0]["text"] == "Kal appointment chahiye"
    by_metric = {item["metric"]: item for item in body["evaluations"]}
    assert by_metric["correctness"]["score"] == 0.9
    assert by_metric["politeness"]["score"] == 1.0
    assert by_metric["missed_handoffs"]["score"] == 0.0
    assert body["recording_available"] is False


async def test_call_detail_is_clinic_scoped(client, db_session, clinic, auth_headers):
    await _seed_calls(db_session, clinic)
    other = Clinic(name="Other Clinic", timezone="Asia/Kolkata")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    call = _call(
        other.id,
        started_at=datetime.now(UTC),
        outcome="booked",
        language="en-IN",
        cost="1.0000",
        duration_seconds=60,
    )
    db_session.add(call)
    await db_session.commit()
    await db_session.refresh(call)

    response = await client.get(f"/api/v1/calls/{call.id}", headers=auth_headers)
    assert response.status_code == 404


async def test_call_recording_redirects_to_source(client, db_session, clinic, auth_headers):
    _, transferred = await _seed_calls(db_session, clinic)

    response = await client.get(
        f"/api/v1/calls/{transferred.id}/recording",
        headers=auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == "https://recordings.example.com/call.ogg"


async def test_call_recording_returns_404_when_missing(client, db_session, clinic, auth_headers):
    booked, _ = await _seed_calls(db_session, clinic)

    response = await client.get(f"/api/v1/calls/{booked.id}/recording", headers=auth_headers)
    assert response.status_code == 404
