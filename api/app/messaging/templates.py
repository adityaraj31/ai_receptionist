from __future__ import annotations

from datetime import datetime
from string import Formatter
from zoneinfo import ZoneInfo

TEMPLATE_VARIABLES = (
    "patient_name",
    "doctor_name",
    "clinic_name",
    "clinic_phone",
    "appointment_time",
)

DEFAULT_CONFIRMATION_EN = (
    "Hi {patient_name}, your appointment with {doctor_name} at {clinic_name} is "
    "confirmed for {appointment_time}. Call {clinic_phone} if you need to change it."
)
DEFAULT_CONFIRMATION_HI = (
    "नमस्ते {patient_name}, {clinic_name} में {doctor_name} के साथ "
    "{appointment_time} पर आपकी अपॉइंटमेंट कन्फर्म हो गई है। "
    "बदलाव के लिए {clinic_phone} पर कॉल करें।"
)
DEFAULT_REMINDER_24H_EN = (
    "Reminder: {patient_name}, you have an appointment with {doctor_name} at "
    "{clinic_name} tomorrow, {appointment_time}. Call {clinic_phone} to reschedule."
)
DEFAULT_REMINDER_24H_HI = (
    "याद दिलाने के लिए: {patient_name}, {clinic_name} में {doctor_name} के साथ "
    "आपकी अपॉइंटमेंट कल {appointment_time} पर है। "
    "बदलाव के लिए {clinic_phone} पर कॉल करें।"
)
DEFAULT_REMINDER_2H_EN = (
    "Reminder: {patient_name}, your appointment with {doctor_name} at {clinic_name} "
    "is at {appointment_time}, in about 2 hours. Call {clinic_phone} if you need help."
)
DEFAULT_REMINDER_2H_HI = (
    "याद दिलाने के लिए: {patient_name}, {clinic_name} में {doctor_name} के साथ "
    "आपकी अपॉइंटमेंट {appointment_time} पर है, लगभग 2 घंटे में। "
    "मदद के लिए {clinic_phone} पर कॉल करें।"
)


class TemplateError(ValueError):
    pass


def default_templates() -> dict[str, str]:
    return {
        "confirmation_template_en": DEFAULT_CONFIRMATION_EN,
        "confirmation_template_hi": DEFAULT_CONFIRMATION_HI,
        "reminder_24h_template_en": DEFAULT_REMINDER_24H_EN,
        "reminder_24h_template_hi": DEFAULT_REMINDER_24H_HI,
        "reminder_2h_template_en": DEFAULT_REMINDER_2H_EN,
        "reminder_2h_template_hi": DEFAULT_REMINDER_2H_HI,
    }


def validate_template(value: str) -> str:
    try:
        parsed = list(Formatter().parse(value))
    except ValueError as exc:
        raise TemplateError("Template has unbalanced braces.") from exc

    for _, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in TEMPLATE_VARIABLES:
            allowed = ", ".join(TEMPLATE_VARIABLES)
            raise TemplateError(f"Unknown template variable {{{field_name}}}. Use: {allowed}.")
        if format_spec or conversion:
            raise TemplateError("Template variables do not support formatting.")
    if not value.strip():
        raise TemplateError("Template cannot be blank.")
    return value


def render_template(value: str, context: dict[str, str]) -> str:
    validate_template(value)
    return value.format_map({key: context.get(key, "") for key in TEMPLATE_VARIABLES})


def format_appointment_time(starts_at: datetime, timezone: str) -> str:
    try:
        local = starts_at.astimezone(ZoneInfo(timezone))
    except Exception:
        local = starts_at
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local:%a %d %b}, {hour}:{local:%M %p}"
