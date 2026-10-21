from __future__ import annotations

import asyncio
from typing import Any

from transfer import SipWarmTransfer


class FakeIO:
    def __init__(self) -> None:
        self.audio_enabled = True

    def set_audio_enabled(self, enabled: bool) -> None:
        self.audio_enabled = enabled


class FakeSession:
    def __init__(self) -> None:
        self.input = FakeIO()
        self.output = FakeIO()
        self.said: list[str] = []

    async def say(self, text: str, **_: Any) -> None:
        self.said.append(text)


class FakeSIP:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[Any] = []

    async def create_sip_participant(self, request: Any, **_: Any) -> None:
        self.requests.append(request)
        if self.error is not None:
            raise self.error


class FakeApi:
    def __init__(self, error: Exception | None = None) -> None:
        self.sip = FakeSIP(error)


class FakeRoom:
    name = "call-test"

    def __init__(self) -> None:
        self.remote_participants: dict[str, Any] = {}
        self.listeners: list[Any] = []

    def on(self, _event: str, listener: Any) -> None:
        self.listeners.append(listener)

    def off(self, _event: str, listener: Any) -> None:
        self.listeners.remove(listener)


class FakeCtx:
    def __init__(self, error: Exception | None = None, fake_job: bool = False) -> None:
        self.room = FakeRoom()
        self.api = FakeApi(error)
        self.fake_job = fake_job
        self.shutdown_called = False

    def is_fake_job(self) -> bool:
        return self.fake_job

    def shutdown(self) -> None:
        self.shutdown_called = True


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def make_transfer(ctx: FakeCtx, session: FakeSession, **kwargs: Any) -> SipWarmTransfer:
    return SipWarmTransfer(
        ctx=ctx,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
        trunk_id=kwargs.pop("trunk_id", "ST_test"),
        caller_id=kwargs.pop("caller_id", "+918069000000"),
        ring_timeout=kwargs.pop("ring_timeout", 20),
        **kwargs,
    )


def test_transfer_dials_front_desk_into_caller_room() -> None:
    ctx = FakeCtx()
    session = FakeSession()

    outcome = run(make_transfer(ctx, session).transfer("+918069000001", "asks for a human"))

    assert outcome.ok is True
    assert session.said == ["Please hold while I connect you to the clinic front desk."]
    assert session.input.audio_enabled is False
    assert session.output.audio_enabled is False
    request = ctx.api.sip.requests[0]
    assert request.room_name == "call-test"
    assert request.sip_call_to == "+918069000001"
    assert request.sip_trunk_id == "ST_test"
    assert request.sip_number == "+918069000000"
    assert request.wait_until_answered is True
    assert request.ringing_timeout.seconds == 20


def test_transfer_re_enables_audio_when_front_desk_does_not_answer() -> None:
    ctx = FakeCtx(error=RuntimeError("no answer"))
    session = FakeSession()

    outcome = run(make_transfer(ctx, session).transfer("+918069000001", "emergency"))

    assert outcome.ok is False
    assert outcome.reason == "no_answer"
    assert session.input.audio_enabled is True
    assert session.output.audio_enabled is True


def test_transfer_requires_outbound_trunk() -> None:
    ctx = FakeCtx()
    session = FakeSession()

    outcome = run(make_transfer(ctx, session, trunk_id="").transfer("+918069000001", "emergency"))

    assert outcome.ok is False
    assert outcome.reason == "not_configured"
    assert ctx.api.sip.requests == []


def test_transfer_skips_fake_jobs() -> None:
    ctx = FakeCtx(fake_job=True)
    session = FakeSession()

    outcome = run(make_transfer(ctx, session).transfer("+918069000001", "emergency"))

    assert outcome.ok is False
    assert outcome.reason == "not_available"
    assert ctx.api.sip.requests == []
