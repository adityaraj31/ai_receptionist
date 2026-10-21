from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

Channel = Literal["whatsapp", "sms"]


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    provider: str
    message_id: str | None = None
    error: str | None = None


class MessageProvider(Protocol):
    name: str

    async def send(self, to: str, body: str) -> DeliveryResult: ...


class MessagingService:
    """One send interface over WhatsApp and SMS provider adapters."""

    def __init__(
        self,
        *,
        whatsapp: MessageProvider | None = None,
        sms: MessageProvider | None = None,
    ) -> None:
        self._providers: dict[str, MessageProvider | None] = {
            "whatsapp": whatsapp,
            "sms": sms,
        }

    async def send(self, channel: Channel, *, to: str, body: str) -> DeliveryResult:
        provider = self._providers.get(channel)
        if provider is None:
            return DeliveryResult(
                ok=False,
                provider="none",
                error=f"{channel}_provider_not_configured",
            )
        try:
            return await provider.send(to, body)
        except Exception as exc:
            return DeliveryResult(
                ok=False,
                provider=provider.name,
                error=f"provider_error: {exc!r}",
            )
