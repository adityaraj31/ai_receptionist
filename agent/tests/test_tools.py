from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from agent_tools import ReceptionistAgent
from api_client import AgentApiClient
from prompts import ClinicConfig, Doctor
from transfer import TransferOutcome

DOCTOR_ID = "11111111-1111-1111-1111-111111111111"
OTHER_DOCTOR_ID = "22222222-2222-2222-2222-222222222222"
APPOINTMENT_ID = "33333333-3333-3333-3333-333333333333"
DAY = "2026-10-22"
SLOT_START = f"{DAY}T10:00:00+05:30"
SLOT_END = f"{DAY}T10:15:00+05:30"


def make_config(
    doctors: tuple[Doctor, ...] | None = None,
    front_desk_number: str = "",
) -> ClinicConfig:
    return ClinicConfig(
        name="Demo Family Clinic",
        doctors=doctors
        or (
            Doctor(name="Dr. Asha Rao", specialty="General Medicine", id=DOCTOR_ID),
            Doctor(name="Dr. Vikram Shah", specialty="Pediatrics", id=OTHER_DOCTOR_ID),
        ),
        timings={"Monday": "09:00-18:00"},
        timezone="Asia/Kolkata",
        front_desk_number=front_desk_number,
    )


def make_agent(
    handler: Any,
    config: ClinicConfig | None = None,
    transfer: Any = None,
) -> ReceptionistAgent:
    transport = httpx.MockTransport(handler)
    api = AgentApiClient("http://api.test", "test-key", transport=transport)
    return ReceptionistAgent(
        clinic_config=config or make_config(),
        api=api,
        transfer=transfer,
    )


class FakeTransfer:
    def __init__(self, outcome: TransferOutcome) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str]] = []

    async def transfer(self, number: str, reason: str) -> TransferOutcome:
        self.calls.append((number, reason))
        return self.outcome


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


def run_tool(agent: ReceptionistAgent, tool_name: str, **kwargs: Any) -> dict[str, Any]:
    async def scenario() -> dict[str, Any]:
        try:
            return await getattr(agent, tool_name)(**kwargs)
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


def test_search_faq_returns_short_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/agent/faq/search"
        assert request.headers["x-service-key"] == "test-key"
        assert json.loads(request.content) == {"query": "Do you have parking?"}
        return httpx.Response(
            200,
            json={
                "found": True,
                "answer": "Free parking is available in the basement.",
                "question": "Where can I park?",
                "score": 0.82,
                "latency_ms": 42,
            },
        )

    result = run_tool(make_agent(handler), "search_faq", question="Do you have parking?")

    assert result == {
        "ok": True,
        "found": True,
        "answer": "Free parking is available in the basement.",
    }


def test_search_faq_no_match_offers_callback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"found": False, "latency_ms": 30})

    result = run_tool(make_agent(handler), "search_faq", question="Do you do MRI?")

    assert result["ok"] is True
    assert result["found"] is False
    assert "call you back" in result["say"]


def test_search_faq_failure_returns_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    result = run_tool(make_agent(handler), "search_faq", question="timings")

    assert result["ok"] is False
    assert result["reason"] == "unavailable"
    assert "call you back" in result["say"]


def test_transfer_to_human_dials_front_desk() -> None:
    transfer = FakeTransfer(TransferOutcome(True, "connected"))
    agent = make_agent(
        lambda request: httpx.Response(500),
        make_config(front_desk_number="+918069000000"),
        transfer,
    )

    result = run_tool(agent, "transfer_to_human", reason="caller asks for a human")

    assert result == {"ok": True, "transferred": True, "reason": "caller asks for a human"}
    assert transfer.calls == [("+918069000000", "caller asks for a human")]


def test_transfer_to_human_without_front_desk_takes_callback() -> None:
    transfer = FakeTransfer(TransferOutcome(True, "connected"))
    agent = make_agent(lambda request: httpx.Response(500), transfer=transfer)

    result = run_tool(agent, "transfer_to_human", reason="emergency")

    assert result["ok"] is False
    assert result["reason"] == "not_configured"
    assert "front desk" in result["say"]
    assert transfer.calls == []


def test_transfer_to_human_reports_no_answer() -> None:
    transfer = FakeTransfer(TransferOutcome(False, "no_answer"))
    agent = make_agent(
        lambda request: httpx.Response(500),
        make_config(front_desk_number="+918069000000"),
        transfer,
    )

    result = run_tool(agent, "transfer_to_human", reason="asks for a human")

    assert result["ok"] is False
    assert result["reason"] == "no_answer"
    assert "call you back" in result["say"]


def test_create_callback_posts_caller_details() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/agent/callbacks"
        captured.update(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "id": "66666666-6666-6666-6666-666666666666",
                "caller_name": "Ravi Kumar",
                "phone": "+919000000000",
                "reason": "transfer_no_answer",
                "message": "Call after 5 PM.",
                "status": "pending",
                "source": "agent",
                "created_at": "2026-10-21T10:00:00Z",
                "updated_at": "2026-10-21T10:00:00Z",
            },
        )

    result = run_tool(
        make_agent(handler),
        "create_callback",
        name="Ravi Kumar",
        phone="+919000000000",
        reason="transfer_no_answer",
        message="Call after 5 PM.",
    )

    assert result["ok"] is True
    assert result["status"] == "pending"
    assert result["callback_id"] == "66666666-6666-6666-6666-666666666666"
    assert captured == {
        "caller_name": "Ravi Kumar",
        "phone": "+919000000000",
        "reason": "transfer_no_answer",
        "message": "Call after 5 PM.",
    }


def test_create_callback_failure_does_not_confirm() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    result = run_tool(
        make_agent(handler),
        "create_callback",
        name="Ravi Kumar",
        phone="+919000000000",
        reason="transfer_no_answer",
    )

    assert result["ok"] is False
    assert result["reason"] == "unavailable"
    assert "couldn't save" in result["say"]
