from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from agent_tools import ReceptionistAgent
from api_client import AgentApiClient
from prompts import ClinicConfig, Doctor

DOCTOR_ID = "11111111-1111-1111-1111-111111111111"
OTHER_DOCTOR_ID = "22222222-2222-2222-2222-222222222222"
APPOINTMENT_ID = "33333333-3333-3333-3333-333333333333"
DAY = "2026-10-22"
SLOT_START = f"{DAY}T10:00:00+05:30"
SLOT_END = f"{DAY}T10:15:00+05:30"


def make_config(doctors: tuple[Doctor, ...] | None = None) -> ClinicConfig:
    return ClinicConfig(
        name="Demo Family Clinic",
        doctors=doctors
        or (
            Doctor(name="Dr. Asha Rao", specialty="General Medicine", id=DOCTOR_ID),
            Doctor(name="Dr. Vikram Shah", specialty="Pediatrics", id=OTHER_DOCTOR_ID),
        ),
        timings={"Monday": "09:00-18:00"},
        timezone="Asia/Kolkata",
    )


def make_agent(handler: Any, config: ClinicConfig | None = None) -> ReceptionistAgent:
    transport = httpx.MockTransport(handler)
    api = AgentApiClient("http://api.test", "test-key", transport=transport)
    return ReceptionistAgent(clinic_config=config or make_config(), api=api)


def slot(starts_at: str = SLOT_START, ends_at: str = SLOT_END) -> dict[str, Any]:
    return {
        "doctor_id": DOCTOR_ID,
        "slot_date": DAY,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "slot_minutes": 15,
        "timezone": "Asia/Kolkata",
    }


def appointment() -> dict[str, Any]:
    return {
        "id": APPOINTMENT_ID,
        "clinic_id": "44444444-4444-4444-4444-444444444444",
        "doctor_id": DOCTOR_ID,
        "doctor_name": "Dr. Asha Rao",
        "doctor_specialization": "General Medicine",
        "patient_id": "55555555-5555-5555-5555-555555555555",
        "patient_name": "Ravi Kumar",
        "patient_phone": "+919999999999",
        "starts_at": SLOT_START,
        "ends_at": SLOT_END,
        "status": "booked",
        "source": "agent",
        "notes": "",
        "fee": "500.00",
    }


def run_tool(agent: ReceptionistAgent, name: str, **kwargs: Any) -> dict[str, Any]:
    async def scenario() -> dict[str, Any]:
        try:
            return await getattr(agent, name)(**kwargs)
        finally:
            await agent._api.aclose()

    return asyncio.run(scenario())


def test_check_availability_returns_short_slots() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/v1/doctors/{DOCTOR_ID}/free-slots"
        assert request.url.params["date"] == DAY
        assert request.headers["x-service-key"] == "test-key"
        return httpx.Response(200, json=[slot()])

    result = run_tool(
        make_agent(handler),
        "check_availability",
        date=DAY,
        doctor="Dr. Asha Rao",
    )

    assert result["ok"] is True
    assert result["doctor"] == "Dr. Asha Rao"
    assert result["slots"] == ["10:00"]
    assert result["timezone"] == "Asia/Kolkata"


def test_check_availability_uses_any_doctor_with_slots() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if DOCTOR_ID in request.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[slot()])

    result = run_tool(make_agent(handler), "check_availability", date=DAY)

    assert result["ok"] is True
    assert result["doctor"] == "Dr. Vikram Shah"
    assert seen == [
        f"/api/v1/doctors/{DOCTOR_ID}/free-slots",
        f"/api/v1/doctors/{OTHER_DOCTOR_ID}/free-slots",
    ]


def test_book_appointment_matches_slot_and_posts_payload() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[slot()])
        captured.update(json.loads(request.content))
        return httpx.Response(201, json=appointment())

    result = run_tool(
        make_agent(handler),
        "book_appointment",
        patient_name="Ravi Kumar",
        phone="+919999999999",
        doctor="Dr. Asha Rao",
        datetime="2026-10-22T10:00",
    )

    assert result == {
        "ok": True,
        "appointment_id": APPOINTMENT_ID,
        "doctor": "Dr. Asha Rao",
        "datetime": SLOT_START,
        "status": "booked",
    }
    assert captured == {
        "doctor_id": DOCTOR_ID,
        "starts_at": SLOT_START,
        "ends_at": SLOT_END,
        "patient_name": "Ravi Kumar",
        "patient_phone": "+919999999999",
    }


def test_book_appointment_reports_unavailable_slot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    result = run_tool(
        make_agent(handler),
        "book_appointment",
        patient_name="Ravi Kumar",
        phone="+919999999999",
        doctor="Dr. Asha Rao",
        datetime="2026-10-22T10:00",
    )

    assert result["ok"] is False
    assert result["reason"] == "slot_unavailable"
    assert result["say"]


def test_reschedule_appointment_resolves_doctor_from_reference() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "/appointments/" in request.url.path:
            return httpx.Response(200, json=appointment())
        if request.method == "GET":
            return httpx.Response(200, json=[slot()])
        captured.update(json.loads(request.content))
        moved = appointment()
        moved["starts_at"] = SLOT_START
        return httpx.Response(200, json=moved)

    result = run_tool(
        make_agent(handler),
        "reschedule_appointment",
        appointment_id=APPOINTMENT_ID,
        datetime="2026-10-22T10:00",
    )

    assert result["ok"] is True
    assert result["appointment_id"] == APPOINTMENT_ID
    assert captured == {"starts_at": SLOT_START, "ends_at": SLOT_END}


def test_cancel_appointment_returns_short_result() -> None:
    cancelled = appointment()
    cancelled["status"] = "cancelled"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=appointment())
        return httpx.Response(200, json=cancelled)

    result = run_tool(
        make_agent(handler),
        "cancel_appointment",
        appointment_id=APPOINTMENT_ID,
    )

    assert result == {
        "ok": True,
        "appointment_id": APPOINTMENT_ID,
        "doctor": "Dr. Asha Rao",
        "datetime": SLOT_START,
        "status": "cancelled",
    }


def test_unknown_doctor_returns_natural_prompt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("API should not be called for an unknown doctor")

    result = run_tool(
        make_agent(handler),
        "check_availability",
        date=DAY,
        doctor="Dr. Nobody",
    )

    assert result["ok"] is False
    assert result["reason"] == "unknown_doctor"
    assert "Dr. Asha Rao" in result["doctors"]
    assert result["say"]


def test_api_failure_returns_fallback_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("api down", request=request)

    result = run_tool(
        make_agent(handler),
        "book_appointment",
        patient_name="Ravi Kumar",
        phone="+919999999999",
        doctor="Dr. Asha Rao",
        datetime="2026-10-22T10:00",
    )

    assert result["ok"] is False
    assert result["reason"] == "unavailable"
    assert "call you back" in result["say"]


def test_invalid_datetime_returns_clarifying_line() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("API should not be called for an invalid datetime")

    result = run_tool(
        make_agent(handler),
        "book_appointment",
        patient_name="Ravi Kumar",
        phone="+919999999999",
        doctor="Dr. Asha Rao",
        datetime="sometime tomorrow",
    )

    assert result["ok"] is False
    assert result["reason"] == "invalid_datetime"
    assert result["say"]
