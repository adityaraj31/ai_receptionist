from ..config import settings
from .base import MessagingService
from .providers import (
    ExotelSmsProvider,
    FakeMessagingProvider,
    GupshupWhatsAppProvider,
    MetaWhatsAppProvider,
    PlivoSmsProvider,
)


def build_messaging_service() -> MessagingService:
    whatsapp = None
    provider = settings.whatsapp_provider.strip().lower()
    if provider == "meta":
        whatsapp = MetaWhatsAppProvider(
            settings.whatsapp_api_url,
            settings.whatsapp_phone_number_id,
            settings.whatsapp_access_token,
            settings.messaging_timeout_seconds,
        )
    elif provider == "gupshup":
        whatsapp = GupshupWhatsAppProvider(
            settings.gupshup_api_url,
            settings.gupshup_api_key,
            settings.gupshup_app_name,
            settings.gupshup_source_number,
            settings.messaging_timeout_seconds,
        )
    elif provider == "fake":
        whatsapp = FakeMessagingProvider("whatsapp")

    sms = None
    provider = settings.sms_provider.strip().lower()
    if provider == "exotel":
        sms = ExotelSmsProvider(
            settings.exotel_subdomain,
            settings.exotel_sid,
            settings.exotel_api_key,
            settings.exotel_api_token,
            settings.exotel_caller_id,
            settings.messaging_timeout_seconds,
        )
    elif provider == "plivo":
        sms = PlivoSmsProvider(
            settings.plivo_auth_id,
            settings.plivo_auth_token,
            settings.plivo_number,
            settings.messaging_timeout_seconds,
        )
    elif provider == "fake":
        sms = FakeMessagingProvider("sms")

    return MessagingService(whatsapp=whatsapp, sms=sms)
