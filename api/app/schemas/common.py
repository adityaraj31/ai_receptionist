import re

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    detail: str


def normalize_phone(value: str) -> str:
    """Normalize a dialable number to E.164-ish text.

    Keeps a leading ``+`` and rejects values that cannot be dialed. SIP URIs are
    deliberately not accepted here; the front desk is a phone number.
    """
    cleaned = re.sub(r"[\s().-]", "", value.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = cleaned[1:] if cleaned.startswith("+") else cleaned
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number with 7 to 15 digits.")
    return f"+{digits}" if cleaned.startswith("+") else digits
