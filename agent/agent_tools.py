"""Function tools exposed to the voice LLM.

Tools never raise into the call. Every failure returns a short structured dict with
``ok=false`` and a ``say`` line, so the model can respond naturally instead of going
silent.
"""

from __future__ import annotations

import re
from datetime import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from livekit.agents import Agent, llm

from api_client import AgentApiError, AgentApiRejected
from prompts import ClinicConfig, Doctor, build_system_prompt

FALLBACK_SAY = (
    "Sorry, I couldn't complete that right now. "
    "May I take your name and number so the clinic team can call you back?"
)
NO_DOCTORS_SAY = (
    "I don't have the doctor list available right now. "
    "May I take your name and number so the clinic team can call you back?"
)


class ReceptionistAgent(Agent):
    """LiveKit agent whose prompt and tools are backed by the clinic API."""

    def __init__(self, *, clinic_config: ClinicConfig, api: Any) -> None:
        self._clinic = clinic_config
        self._api = api
        super().__init__(instructions=build_system_prompt(clinic_config))

    @llm.function_tool
    async def check_availability(self, date: str, doctor: str = "") -> dict[str, Any]:
        """Find free appointment slots for a doctor on a date.

        Args:
            date: Local date in YYYY-MM-DD format.
            doctor: Doctor name. Leave empty to use any available doctor.
        """
        timezone = self._timezone()
        try:
            slots_by_doctor = await self._slots_for(date, doctor)
        except _ToolProblem as problem:
            return problem.result

        if slots_by_doctor is None:
            return _failure(
                "invalid_date",
                "I didn't catch that date clearly. Which day would you like?",
            )

        doctor_name, slots = slots_by_doctor
        if not slots:
            return {
                "ok": True,
                "doctor": doctor_name,
                "date": date,
                "timezone": timezone,
                "slots": [],
                "message": "No free slots on that date. Try another day.",
            }

        return {
            "ok": True,
            "doctor": doctor_name,
            "date": date,
            "timezone": timezone,
            "slots": [slot["starts_at"][11:16] for slot in slots[:5]],
        }

    @llm.function_tool
    async def book_appointment(
        self,
        patient_name: str,
        phone: str,
        doctor: str,
        datetime: str,
    ) -> dict[str, Any]:
        """Book an appointment after the caller confirms the details.

        Args:
            patient_name: Patient's full name.
            phone: Callback phone number.
            doctor: Doctor name.
            datetime: Local start time in YYYY-MM-DDTHH:MM format.
        """
        try:
            start = self._parse_local_datetime(datetime)
        except ValueError:
            return _failure(
                "invalid_datetime",
                "I didn't catch the date and time clearly. Could you repeat it?",
            )

        doctor_config = self._resolve_doctor(doctor)
        if doctor_config is None or not doctor_config.id:
            return self._unknown_doctor()

        try:
            slots = await self._api.free_slots(doctor_config.id, start.date().isoformat())
        except AgentApiRejected:
            return _failure(
                "invalid_date",
                "I didn't catch that date clearly. Which day would you like?",
            )
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        match = _matching_slot(slots, start)
        if match is None:
            return _slot_unavailable(
                doctor_config.name,
                [slot["starts_at"][11:16] for slot in slots[:3]],
            )

        payload = {
            "doctor_id": doctor_config.id,
            "starts_at": match["starts_at"],
            "ends_at": match["ends_at"],
            "patient_name": patient_name.strip(),
            "patient_phone": phone.strip(),
        }
        try:
            appointment = await self._api.book_appointment(payload)
        except AgentApiRejected as exc:
            if exc.status_code == 409:
                return _slot_unavailable(doctor_config.name, [])
            return _failure("rejected", FALLBACK_SAY)
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        return {
            "ok": True,
            "appointment_id": appointment["id"],
            "doctor": appointment["doctor_name"],
            "datetime": appointment["starts_at"],
            "status": appointment["status"],
        }

    @llm.function_tool
    async def reschedule_appointment(
        self,
        appointment_id: str,
        datetime: str,
    ) -> dict[str, Any]:
        """Move an existing appointment to a new slot.

        Args:
            appointment_id: Appointment reference from an earlier booking.
            datetime: New local start time in YYYY-MM-DDTHH:MM format.
        """
        try:
            start = self._parse_local_datetime(datetime)
        except ValueError:
            return _failure(
                "invalid_datetime",
                "I didn't catch the date and time clearly. Could you repeat it?",
            )

        try:
            appointment = await self._api.get_appointment(appointment_id)
        except AgentApiRejected:
            return _appointment_not_found()
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        doctor_id = appointment.get("doctor_id")
        if not doctor_id:
            return _appointment_not_found()

        try:
            slots = await self._api.free_slots(doctor_id, start.date().isoformat())
        except AgentApiRejected:
            return _failure(
                "invalid_date",
                "I didn't catch that date clearly. Which day would you like?",
            )
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        match = _matching_slot(slots, start)
        if match is None:
            return _slot_unavailable(
                appointment.get("doctor_name", "the doctor"),
                [slot["starts_at"][11:16] for slot in slots[:3]],
            )

        try:
            moved = await self._api.reschedule_appointment(
                appointment_id,
                {"starts_at": match["starts_at"], "ends_at": match["ends_at"]},
            )
        except AgentApiRejected as exc:
            if exc.status_code == 409:
                return _slot_unavailable(appointment.get("doctor_name", "the doctor"), [])
            return _failure("rejected", FALLBACK_SAY)
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        return {
            "ok": True,
            "appointment_id": moved["id"],
            "doctor": moved["doctor_name"],
            "datetime": moved["starts_at"],
            "status": moved["status"],
        }

    @llm.function_tool
    async def cancel_appointment(self, appointment_id: str) -> dict[str, Any]:
        """Cancel an existing appointment.

        Args:
            appointment_id: Appointment reference from an earlier booking.
        """
        try:
            appointment = await self._api.get_appointment(appointment_id)
        except AgentApiRejected:
            return _appointment_not_found()
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        try:
            cancelled = await self._api.cancel_appointment(appointment_id)
        except AgentApiRejected:
            return _appointment_not_found()
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        return {
            "ok": True,
            "appointment_id": cancelled["id"],
            "doctor": appointment.get("doctor_name", ""),
            "datetime": cancelled.get("starts_at", ""),
            "status": cancelled["status"],
        }

    async def _slots_for(
        self,
        date: str,
        doctor: str,
    ) -> tuple[str, list[dict[str, Any]]] | None:
        candidates: list[Doctor]
        if doctor.strip():
            resolved = self._resolve_doctor(doctor)
            if resolved is None or not resolved.id:
                raise _ToolProblem(self._unknown_doctor())
            candidates = [resolved]
        else:
            candidates = [item for item in self._clinic.doctors if item.id]

        if not candidates:
            raise _ToolProblem(_failure("no_doctors", NO_DOCTORS_SAY))

        last_error: AgentApiError | None = None
        for candidate in candidates:
            try:
                slots = await self._api.free_slots(candidate.id, date)
            except AgentApiRejected:
                return None
            except AgentApiError as exc:
                last_error = exc
                continue
            if slots or candidate is candidates[-1]:
                return candidate.name, slots

        if last_error is not None:
            raise _ToolProblem(_failure("unavailable", FALLBACK_SAY))
        return candidates[0].name, []

    def _resolve_doctor(self, name: str) -> Doctor | None:
        query = _normalize(name)
        if not query:
            return None
        for doctor in self._clinic.doctors:
            candidate = _normalize(doctor.name)
            if query == candidate or query in candidate or candidate in query:
                return doctor
        return None

    def _unknown_doctor(self) -> dict[str, Any]:
        return _failure(
            "unknown_doctor",
            "I don't have that doctor listed. Which doctor would you like?",
            doctors=[doctor.name for doctor in self._clinic.doctors],
        )

    def _parse_local_datetime(self, value: str) -> dt:
        text = value.strip().replace(" ", "T")
        parsed = dt.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._tz())
        return parsed.astimezone(self._tz())

    def _tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self._clinic.timezone)
        except ZoneInfoNotFoundError:
            return ZoneInfo("Asia/Kolkata")

    def _timezone(self) -> str:
        return self._clinic.timezone or "Asia/Kolkata"


class _ToolProblem(Exception):
    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__(result.get("reason", "tool_error"))
        self.result = result


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _matching_slot(
    slots: list[dict[str, Any]],
    start: dt,
) -> dict[str, Any] | None:
    for slot in slots:
        if _same_instant(slot.get("starts_at"), start):
            return slot
    return None


def _same_instant(value: Any, start: dt) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return dt.fromisoformat(value) == start
    except ValueError:
        return False


def _failure(reason: str, say: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "reason": reason, "say": say, **extra}


def _slot_unavailable(doctor: str, alternatives: list[str]) -> dict[str, Any]:
    result = _failure(
        "slot_unavailable",
        "That time isn't free. Would you like the next available slot?",
        doctor=doctor,
    )
    if alternatives:
        result["alternatives"] = alternatives
    return result


def _appointment_not_found() -> dict[str, Any]:
    return _failure(
        "not_found",
        "I couldn't find that appointment. Let me take your details and have the clinic "
        "call you back.",
    )
