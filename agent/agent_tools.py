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
from transfer import TransferService

FALLBACK_SAY = (
    "Sorry, I couldn't complete that right now. "
    "May I take your name and number so the clinic team can call you back?"
)
NO_DOCTORS_SAY = (
    "I don't have the doctor list available right now. "
    "May I take your name and number so the clinic team can call you back?"
)
TRANSFER_UNAVAILABLE_SAY = (
    "I couldn't reach the front desk. "
    "May I take your name and number so the clinic team can call you back?"
)
CALLBACK_SAVE_FAILED_SAY = (
    "I'm sorry, I couldn't save those details. Please call the clinic and the team will help you."
)


class ReceptionistAgent(Agent):
    """LiveKit agent whose prompt and tools are backed by the clinic API."""

    def __init__(
        self,
        *,
        clinic_config: ClinicConfig,
        api: Any,
        transfer: TransferService | None = None,
    ) -> None:
        self._clinic = clinic_config
        self._api = api
        self._transfer = transfer
        super().__init__(instructions=build_system_prompt(clinic_config))

    @llm.function_tool
    async def search_faq(self, question: str) -> dict[str, Any]:
        """Look up clinic information such as timings, fees, address, services, or policies.

        Args:
            question: The caller's question, in their own words.
        """
        try:
            result = await self._api.search_faq(question)
        except AgentApiRejected:
            return _failure("rejected", FALLBACK_SAY)
        except AgentApiError:
            return _failure("unavailable", FALLBACK_SAY)

        if not result.get("found"):
            return {
                "ok": True,
                "found": False,
                "say": (
                    "I don't have that information right now. "
                    "The clinic team can call you back with the details."
                ),
            }

        return {
            "ok": True,
            "found": True,
            "answer": result.get("answer", ""),
        }

    @llm.function_tool
    async def transfer_to_human(self, reason: str) -> dict[str, Any]:
        """Transfer the caller to the clinic front desk and wait for an answer.

        Use this for emergencies, explicit requests for a human, billing or insurance
        questions, repeated frustration, or after two failed attempts to understand.
        If the front desk does not answer, take a callback instead.

        Args:
            reason: Short reason for the transfer, such as "emergency" or "asks for a human".
        """
        if self._transfer is None:
            return _failure("not_configured", TRANSFER_UNAVAILABLE_SAY)
        if not self._clinic.front_desk_number:
            return _failure("not_configured", TRANSFER_UNAVAILABLE_SAY)

        try:
            outcome = await self._transfer.transfer(
                self._clinic.front_desk_number,
                reason.strip() or "caller requested a human",
            )
        except Exception:
            return _failure("transfer_error", TRANSFER_UNAVAILABLE_SAY)

        if not outcome.ok:
            return _failure(outcome.reason or "transfer_failed", TRANSFER_UNAVAILABLE_SAY)

        return {"ok": True, "transferred": True, "reason": reason}

    @llm.function_tool
    async def create_callback(
        self,
        name: str,
        phone: str,
        reason: str,
        message: str = "",
    ) -> dict[str, Any]:
        """Create a callback task for the clinic team.

        Use this after a failed transfer, or when the caller asks for a callback.
        Collect the caller's name, phone number, and a short message first.

        Args:
            name: Caller's name.
            phone: Callback phone number.
            reason: Why the caller needs a callback.
            message: One-line message or summary for the clinic team.
        """
        if not name.strip() or not phone.strip():
            return _failure(
                "missing_details",
                "I need both your name and a callback number. Could you share them?",
            )

        try:
            result = await self._api.create_callback(
                {
                    "caller_name": name.strip(),
                    "phone": phone.strip(),
                    "reason": reason.strip(),
                    "message": message.strip(),
                }
            )
        except AgentApiRejected:
            return _failure("rejected", CALLBACK_SAVE_FAILED_SAY)
        except AgentApiError:
            return _failure("unavailable", CALLBACK_SAVE_FAILED_SAY)

        return {
            "ok": True,
            "callback_id": result["id"],
            "status": result["status"],
        }

    @llm.function_tool
    async def send_confirmation(self, channel: str, appointment_id: str) -> dict[str, Any]:
        """Send an appointment confirmation on WhatsApp or SMS.

        Call this only after a successful booking and only if the caller wants a
        confirmation. Use the appointment_id returned by book_appointment.

        Args:
            channel: "whatsapp" or "sms", whichever the caller prefers.
            appointment_id: Appointment reference from book_appointment.
        """
        normalized = channel.strip().lower()
        if normalized not in {"whatsapp", "sms"}:
            return _failure(
                "invalid_channel",
                "Would you like the confirmation on WhatsApp or by SMS?",
            )
        try:
            result = await self._api.send_confirmation(appointment_id, normalized)
        except AgentApiRejected:
            return _failure(
                "rejected",
                "I couldn't send the confirmation. The clinic team can help you.",
            )
        except AgentApiError:
            return _failure(
                "unavailable",
                "I couldn't send the confirmation right now. The appointment is still booked.",
            )

        if not result.get("sent"):
            return _failure(
                str(result.get("reason") or "not_sent"),
                "I couldn't send the confirmation right now. The appointment is still booked.",
            )
        return {"ok": True, "sent": True, "channel": normalized}

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
        language: str = "",
    ) -> dict[str, Any]:
        """Book an appointment after the caller confirms the details.

        Args:
            patient_name: Patient's full name.
            phone: Callback phone number.
            doctor: Doctor name.
            datetime: Local start time in YYYY-MM-DDTHH:MM format.
            language: Caller language, either "hi" or "en". Leave empty if unsure.
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
        if language.strip().lower() in {"en", "hi"}:
            payload["language"] = language.strip().lower()
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
