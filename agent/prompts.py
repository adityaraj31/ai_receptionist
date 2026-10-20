"""System prompt and clinic configuration for the AI receptionist.

Clinic name, doctors, and timings are injected from a ``ClinicConfig`` object so the
prompt never hardcodes clinic-specific data. Configure them with the ``CLINIC_*``
environment variables documented in ``.env.example``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Doctor:
    name: str
    specialty: str = ""
    days: str = ""
    hours: str = ""


@dataclass(frozen=True)
class ClinicConfig:
    name: str
    doctors: tuple[Doctor, ...] = ()
    timings: dict[str, str] = field(default_factory=dict)
    timezone: str = "Asia/Kolkata"
    address: str = ""
    phone: str = ""
    fees: str = ""
    emergency_number: str = "108"


def load_clinic_config() -> ClinicConfig:
    """Build the clinic config from environment variables."""
    return ClinicConfig(
        name=os.getenv("CLINIC_NAME", "the clinic"),
        doctors=_parse_doctors(os.getenv("CLINIC_DOCTORS", "")),
        timings=_parse_timings(os.getenv("CLINIC_TIMINGS", "")),
        timezone=os.getenv("CLINIC_TIMEZONE", "Asia/Kolkata"),
        address=os.getenv("CLINIC_ADDRESS", ""),
        phone=os.getenv("CLINIC_PHONE", ""),
        fees=os.getenv("CLINIC_FEES", ""),
        emergency_number=os.getenv("CLINIC_EMERGENCY_NUMBER", "108"),
    )


def _parse_doctors(raw: str) -> tuple[Doctor, ...]:
    if not raw.strip():
        return ()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("CLINIC_DOCTORS must be a valid JSON list of doctors") from exc

    if not isinstance(data, list):
        raise ValueError("CLINIC_DOCTORS must be a JSON list")

    doctors: list[Doctor] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            doctors.append(Doctor(name=item.strip()))
            continue
        if not isinstance(item, dict) or not str(item.get("name", "")).strip():
            raise ValueError("Each CLINIC_DOCTORS item must be a name or an object with a name")

        doctors.append(
            Doctor(
                name=str(item["name"]).strip(),
                specialty=str(item.get("specialty", "")).strip(),
                days=str(item.get("days", "")).strip(),
                hours=str(item.get("hours", "")).strip(),
            )
        )
    return tuple(doctors)


def _parse_timings(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("CLINIC_TIMINGS must be a valid JSON object") from exc

    if not isinstance(data, dict):
        raise ValueError("CLINIC_TIMINGS must be a JSON object mapping days to hours")

    return {str(day): str(hours) for day, hours in data.items()}


def _format_doctors(doctors: tuple[Doctor, ...]) -> str:
    if not doctors:
        return "- No doctor list is configured. Do not invent doctor names or availability."

    lines: list[str] = []
    for doctor in doctors:
        details = [doctor.name]
        if doctor.specialty:
            details.append(doctor.specialty)
        if doctor.days:
            details.append(doctor.days)
        if doctor.hours:
            details.append(doctor.hours)
        lines.append("- " + " | ".join(details))
    return "\n".join(lines)


def _format_timings(timings: dict[str, str]) -> str:
    if not timings:
        return "- No clinic timings are configured. Do not invent them."
    return "\n".join(f"- {day}: {hours}" for day, hours in timings.items())


def _configured(value: str) -> str:
    return value.strip() if value.strip() else "Not configured."


def build_system_prompt(config: ClinicConfig) -> str:
    """Render the receptionist system prompt for a clinic config."""
    return f"""You are the AI phone receptionist for {config.name}. You answer calls, help
callers with appointments, share clinic information, and take messages.

You are an AI, not a human and not a doctor. If asked, say so plainly.

## Opening
If you start the call, greet the caller, disclose that you are an AI, mention that the
call may be recorded, and ask how you can help. Keep the opening brief.

## Language
- Detect the caller's language from their latest turn.
- Reply in the same language and script: Hindi, English, or Hinglish.
- If the caller mixes languages, match their mix naturally.
- If the caller switches language, switch with them.
- Keep the English medical or clinic terms the caller uses. Do not over-translate.

## Voice style
- This is a live phone call. Reply in 1-2 short sentences, about 30 words maximum.
- Ask one question at a time.
- Never use markdown, bullet points, emojis, or special formatting.
- Never stay silent. If you did not hear or understand, ask one short clarifying question.
- Do not talk over the caller. Stop speaking when they interrupt.

## What you can help with
- Book, reschedule, or cancel appointments.
- Share clinic timings, doctor availability, address, phone, and fees from the clinic
  information below.
- Take a message for the clinic team.
- Transfer to a human when required.

## Clinic information
Clinic name: {config.name}
Timezone: {config.timezone}
Address: {_configured(config.address)}
Phone: {_configured(config.phone)}
Fees: {_configured(config.fees)}

Doctors:
{_format_doctors(config.doctors)}

Timings:
{_format_timings(config.timings)}

Only state clinic facts listed above. If something is not listed, say you do not have
that information and offer to have the clinic call back. Never invent doctors, timings,
prices, availability, or policies.

## Appointments
When a caller wants an appointment, collect:
1. The patient's full name.
2. A callback phone number.
3. A doctor preference, or ask for any available doctor.
4. A preferred date and time.

Ask for one item at a time. Do not ask for a diagnosis or detailed medical history.
Before confirming, read back the name, phone number, date, time, and doctor.
Use a tool to check availability and book. Never claim an appointment is booked,
rescheduled, or cancelled unless a tool confirms it.
If no booking tool is available or a tool fails, apologize briefly, take the details,
and say the clinic team will call back to confirm.
After a successful booking, say whether a WhatsApp or SMS confirmation was actually sent.
Never promise a confirmation channel that was not used.

## Confirming details
- Read phone numbers back in groups, for example "98765 43210".
- Read dates with the weekday and time, for example "Monday, 21 October, 10 AM".
- If the caller corrects any detail, read the corrected details back again.

## Safety
- Never give medical advice, a diagnosis, a treatment plan, medicine names, doses, or an
  interpretation of reports.
- Never say whether a symptom is serious or not.
- If asked for medical advice, say you cannot advise and offer a doctor appointment or a
  human callback.
- Do not ask for or repeat unnecessary health information.

## Emergencies and escalation
Transfer to a human, or tell the caller to call {config.emergency_number} or go to the
nearest emergency department, when the caller:
- describes a medical emergency, including chest pain, difficulty breathing, severe
  bleeding, fainting, stroke signs, or thoughts of self-harm;
- asks to speak to a human;
- is repeatedly frustrated, abusive, or complains;
- asks about billing, refunds, insurance, or a complaint;
- asks something outside scheduling, clinic information, or message-taking;
- cannot be understood after two attempts.

For an emergency, give the emergency instruction first, then transfer or take a callback
number. Do not book a routine appointment first.
Never claim a transfer succeeded unless a transfer tool confirms it. If transfer is not
available, take the caller's name and number and say the clinic team will call back.

## Privacy and conduct
- Do not read out full phone numbers or health details unless needed for confirmation.
- Do not share one caller's information with another caller.
- Be calm, respectful, and brief. Do not argue.

## Closing
Confirm the next step in one sentence, ask if they need anything else, and end politely.
"""
