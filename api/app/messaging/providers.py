from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from uuid import uuid4

import httpx

from .base import DeliveryResult


def _digits(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits


def _error_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:300] or f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
        if isinstance(error, str):
            return error[:300]
        if payload.get("message"):
            return str(payload["message"])[:300]
    return json.dumps(payload)[:300]


logger = logging.getLogger(__name__)


def _mask_phone(value: str) -> str:
    digits = _digits(value)
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"


@dataclass
class FakeMessagingProvider:
    """Local-only provider: logs the message instead of calling a network API."""

    channel: str
    name: str = "fake"

    def __post_init__(self) -> None:
        self.name = f"fake_{self.channel}"

    async def send(self, to: str, body: str) -> DeliveryResult:
        message_id = f"fake-{uuid4().hex[:12]}"
        logger.warning(
            "%s to=%s id=%s body=%s",
            self.name,
            _mask_phone(to),
            message_id,
            body,
        )
        return DeliveryResult(True, self.name, message_id=message_id)


@dataclass
class MetaWhatsAppProvider:
    api_url: str
    phone_number_id: str
    access_token: str
    timeout: float
    transport: httpx.AsyncBaseTransport | None = None
    name = "meta_whatsapp"

    async def send(self, to: str, body: str) -> DeliveryResult:
        if not self.phone_number_id or not self.access_token:
            return DeliveryResult(False, self.name, error="whatsapp_not_configured")

        url = f"{self.api_url.rstrip('/')}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": _digits(to),
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        if response.status_code >= 400:
            return DeliveryResult(False, self.name, error=_error_text(response))
        try:
            message_id = response.json()["messages"][0]["id"]
        except (KeyError, IndexError, TypeError, ValueError):
            message_id = None
        return DeliveryResult(True, self.name, message_id=message_id)


@dataclass
class GupshupWhatsAppProvider:
    api_url: str
    api_key: str
    app_name: str
    source_number: str
    timeout: float
    transport: httpx.AsyncBaseTransport | None = None
    name = "gupshup_whatsapp"

    async def send(self, to: str, body: str) -> DeliveryResult:
        if not self.api_key or not self.source_number:
            return DeliveryResult(False, self.name, error="whatsapp_not_configured")

        payload = {
            "channel": "whatsapp",
            "source": _digits(self.source_number),
            "destination": _digits(to),
            "src.name": self.app_name,
            "message": json.dumps({"type": "text", "text": body}),
        }
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                f"{self.api_url.rstrip('/')}/msg",
                data=payload,
                headers={"apikey": self.api_key},
            )
        if response.status_code >= 400:
            return DeliveryResult(False, self.name, error=_error_text(response))
        try:
            data = response.json()
        except ValueError:
            data = {}
        return DeliveryResult(
            True,
            self.name,
            message_id=str(data.get("messageId") or data.get("id") or "") or None,
        )


@dataclass
class ExotelSmsProvider:
    subdomain: str
    sid: str
    api_key: str
    api_token: str
    caller_id: str
    timeout: float
    transport: httpx.AsyncBaseTransport | None = None
    name = "exotel_sms"

    async def send(self, to: str, body: str) -> DeliveryResult:
        if not self.sid or not self.api_key or not self.api_token or not self.caller_id:
            return DeliveryResult(False, self.name, error="sms_not_configured")

        url = f"https://{self.subdomain}/v1/Accounts/{self.sid}/Sms/send.json"
        payload = {"From": self.caller_id, "To": _digits(to), "Body": body}
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                url,
                data=payload,
                auth=(self.api_key, self.api_token),
            )
        if response.status_code >= 400:
            return DeliveryResult(False, self.name, error=_error_text(response))
        try:
            message = response.json().get("SMSMessage", {})
            message_id = message.get("Sid")
        except (ValueError, AttributeError):
            message_id = None
        return DeliveryResult(True, self.name, message_id=message_id)


@dataclass
class PlivoSmsProvider:
    auth_id: str
    auth_token: str
    source_number: str
    timeout: float
    transport: httpx.AsyncBaseTransport | None = None
    name = "plivo_sms"

    async def send(self, to: str, body: str) -> DeliveryResult:
        if not self.auth_id or not self.auth_token or not self.source_number:
            return DeliveryResult(False, self.name, error="sms_not_configured")

        url = f"https://api.plivo.com/v1/Account/{self.auth_id}/Message/"
        payload = {"src": _digits(self.source_number), "dst": _digits(to), "text": body}
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                url,
                json=payload,
                auth=(self.auth_id, self.auth_token),
            )
        if response.status_code >= 400:
            return DeliveryResult(False, self.name, error=_error_text(response))
        try:
            message_id = response.json().get("message_uuid", [None])[0]
        except (ValueError, AttributeError, IndexError, TypeError):
            message_id = None
        return DeliveryResult(True, self.name, message_id=message_id)
