from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.messaging.base import DeliveryResult
from app.models import MessageLog
from app.services.reminders import plan_reminders, send_appointment_reminder
from tests.test_appointments import add_rule, book


class FakeMessaging:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def send(self, channel, *, to, body):
        self.calls.append((channel, to, body))
        return DeliveryResult(True, "fake", "msg-1")


async def test_messaging_settings_defaults_and_update(client, auth_headers):
    response = await client.get("/api/v1/messaging-settings", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmation_whatsapp_enabled"] is True
    assert body["default_language"] == "en"
    assert "{patient_name}" in body["confirmation_template_en"]
    assert "अपॉइंटमेंट" in body["confirmation_template_hi"]

    updated = await client.patch(
        "/api/v1/messaging-settings",
        json={
            "confirmation_sms_enabled": True,
            "reminders_enabled": False,
            "default_language": "hi",
            "confirmation_template_hi": "नमस्ते {patient_name}, कन्फर्म।",
        },
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["confirmation_sms_enabled"] is True
    assert updated.json()["reminders_enabled"] is False
    assert updated.json()["default_language"] == "hi"


async def test_messaging_settings_reject_unknown_template_variable(client, auth_headers):
    response = await client.patch(
        "/api/v1/messaging-settings",
        json={"confirmation_template_en": "Hi {unknown_variable}"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "Unknown template variable" in response.text


async def test_agent_confirmation_sends_whatsapp(
    client,
    db_session,
    doctor,
    agent_headers,
    auth_headers,
    next_weekday,
    at_time,
    monkeypatch,
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)
    booked = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    fake = FakeMessaging()
    monkeypatch.setattr("app.services.messaging.build_messaging_service", lambda: fake)

    response = await client.post(
        f"/api/v1/agent/appointments/{booked.json()['id']}/confirmation",
        json={"channel": "whatsapp"},
        headers=agent_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["sent"] is True
    assert fake.calls and fake.calls[0][0] == "whatsapp"
    assert "Ravi Kumar" in fake.calls[0][2]

    logs = list((await db_session.scalars(select(MessageLog))).all())
    assert len(logs) == 1


async def test_agent_confirmation_respects_disabled_channel(
    client,
    db_session,
    doctor,
    agent_headers,
    auth_headers,
    next_weekday,
    at_time,
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)
    booked = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    await client.patch(
        "/api/v1/messaging-settings",
        json={"confirmation_whatsapp_enabled": False},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/agent/appointments/{booked.json()['id']}/confirmation",
        json={"channel": "whatsapp"},
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["sent"] is False
    assert response.json()["reason"] == "confirmation_channel_disabled"


async def test_reminder_job_sends_and_is_idempotent(
    client,
    db_session,
    doctor,
    agent_headers,
    next_weekday,
    at_time,
    monkeypatch,
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)
    booked = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
        name="Ravi Kumar",
    )
    fake = FakeMessaging()
    monkeypatch.setattr("app.services.messaging.build_messaging_service", lambda: fake)

    result = await send_appointment_reminder(
        {},
        booked.json()["id"],
        "reminder_24h",
        booked.json()["starts_at"],
    )
    assert result["status"] == "sent"
    assert len(fake.calls) == 1

    again = await send_appointment_reminder(
        {},
        booked.json()["id"],
        "reminder_24h",
        booked.json()["starts_at"],
    )
    assert again["status"] == "sent"
    assert len(fake.calls) == 1


def test_plan_reminders_skips_past_lead_times():
    now = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    starts_at = now + timedelta(hours=3)
    assert [kind for kind, _ in plan_reminders(starts_at, now)] == ["reminder_2h"]

    starts_at = now + timedelta(hours=30)
    assert [kind for kind, _ in plan_reminders(starts_at, now)] == [
        "reminder_24h",
        "reminder_2h",
    ]


async def test_meta_whatsapp_provider_payload():
    import httpx

    from app.messaging.providers import MetaWhatsAppProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    provider = MetaWhatsAppProvider(
        "https://graph.test/v21.0",
        "phone-1",
        "token-1",
        5,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.send("+91 99999 99999", "Hello")

    assert result.ok and result.message_id == "wamid.1"
    assert seen["url"] == "https://graph.test/v21.0/phone-1/messages"
    assert seen["auth"] == "Bearer token-1"
    assert seen["json"]["to"] == "919999999999"
    assert seen["json"]["text"]["body"] == "Hello"


async def test_exotel_sms_provider_payload():
    import httpx

    from app.messaging.providers import ExotelSmsProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["form"] = request.content.decode()
        return httpx.Response(200, json={"SMSMessage": {"Sid": "sms-1"}})

    provider = ExotelSmsProvider(
        "api.exotel.com",
        "sid-1",
        "key-1",
        "token-1",
        "+918069000000",
        5,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.send("+91 99999 99999", "Hello")

    assert result.ok and result.message_id == "sms-1"
    assert "Sms/send.json" in seen["url"]
    assert "To=919999999999" in seen["form"]


async def test_messaging_service_reports_missing_provider():
    from app.messaging.base import MessagingService

    result = await MessagingService().send("whatsapp", to="+919999999999", body="Hi")

    assert result.ok is False
    assert result.error == "whatsapp_provider_not_configured"


async def test_confirmation_uses_hindi_template_for_hindi_booking(
    client,
    db_session,
    doctor,
    agent_headers,
    next_weekday,
    at_time,
    monkeypatch,
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)
    booked = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "starts_at": at_time(day, 9, 0).isoformat(),
            "ends_at": at_time(day, 9, 15).isoformat(),
            "patient_name": "Ravi Kumar",
            "patient_phone": "+919999999999",
            "language": "hi",
        },
        headers=agent_headers,
    )
    assert booked.status_code == 201, booked.text
    fake = FakeMessaging()
    monkeypatch.setattr("app.services.messaging.build_messaging_service", lambda: fake)

    response = await client.post(
        f"/api/v1/agent/appointments/{booked.json()['id']}/confirmation",
        json={"channel": "whatsapp"},
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["sent"] is True
    assert "अपॉइंटमेंट" in fake.calls[0][2]


async def test_fake_provider_logs_instead_of_sending(monkeypatch):
    from app.messaging import providers

    seen = []
    monkeypatch.setattr(providers.logger, "warning", lambda *args, **kwargs: seen.append(args))

    result = await providers.FakeMessagingProvider("whatsapp").send(
        "+91 99999 99999", "Namaste Ravi"
    )

    assert result.ok is True
    assert result.provider == "fake_whatsapp"
    assert result.message_id and result.message_id.startswith("fake-")
    assert seen and seen[0][1] == "fake_whatsapp"
    assert seen[0][2] == "***9999"
    assert seen[0][4] == "Namaste Ravi"


async def test_factory_builds_fake_whatsapp_and_sms(monkeypatch):
    from app.config import settings
    from app.messaging.factory import build_messaging_service

    monkeypatch.setattr(settings, "whatsapp_provider", "fake")
    monkeypatch.setattr(settings, "sms_provider", "fake")
    service = build_messaging_service()

    for channel in ("whatsapp", "sms"):
        result = await service.send(channel, to="+919999999999", body="Hello")
        assert result.ok is True
        assert result.provider == f"fake_{channel}"
