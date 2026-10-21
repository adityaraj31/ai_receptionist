"""Warm SIP transfer to the clinic front desk.

The front desk is dialed into the caller's room with ``wait_until_answered``.
When someone answers, the caller and the front desk talk directly and the
receptionist disables its own audio. If the call is not answered within the
ring window, the tool returns a failure so the LLM can take a callback.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from livekit import api, rtc
from livekit.agents import AgentSession, JobContext

logger = logging.getLogger("receptionist.transfer")

EventLogger = Callable[..., None]


@dataclass(frozen=True)
class TransferOutcome:
    ok: bool
    reason: str = ""
    detail: str = ""


class TransferService(Protocol):
    async def transfer(self, number: str, reason: str) -> TransferOutcome: ...


class SipWarmTransfer:
    def __init__(
        self,
        *,
        ctx: JobContext,
        session: AgentSession,
        trunk_id: str,
        caller_id: str = "",
        ring_timeout: float = 20.0,
        on_event: EventLogger | None = None,
    ) -> None:
        self._ctx = ctx
        self._session = session
        self._trunk_id = trunk_id.strip()
        self._caller_id = caller_id.strip()
        self._ring_timeout = ring_timeout
        self._on_event = on_event
        self._caller_identities: set[str] = set()
        self._front_desk_identity = f"front-desk-{uuid.uuid4().hex[:8]}"
        self._shutting_down = False

    async def transfer(self, number: str, reason: str) -> TransferOutcome:
        number = number.strip()
        if not number:
            return TransferOutcome(False, "not_configured", "No front desk number is configured.")
        if not self._trunk_id:
            return TransferOutcome(
                False,
                "not_configured",
                "LIVEKIT_SIP_OUTBOUND_TRUNK is not configured.",
            )
        if self._ctx.is_fake_job():
            return TransferOutcome(False, "not_available", "SIP transfer needs a live room.")

        self._event("transfer_started", reason=reason, room=self._ctx.room.name)
        self._watch_participants()
        await self._session.say(
            "Please hold while I connect you to the clinic front desk.",
            allow_interruptions=False,
        )
        self._set_io(False)

        request = api.CreateSIPParticipantRequest(
            room_name=self._ctx.room.name,
            participant_identity=self._front_desk_identity,
            participant_name="Front desk",
            sip_trunk_id=self._trunk_id,
            sip_call_to=number,
            wait_until_answered=True,
            play_dialtone=True,
        )
        if self._caller_id:
            request.sip_number = self._caller_id
        request.ringing_timeout.FromNanoseconds(int(self._ring_timeout * 1e9))

        try:
            await self._ctx.api.sip.create_sip_participant(
                request,
                timeout=self._ring_timeout + 10,
            )
        except Exception as exc:
            logger.warning("front desk transfer failed: %r", exc)
            self._event("transfer_failed", reason=reason, error=repr(exc))
            self._set_io(True)
            return TransferOutcome(False, "no_answer", "The front desk did not answer.")

        self._event("transfer_connected", reason=reason, room=self._ctx.room.name)
        return TransferOutcome(True, "connected")

    def _watch_participants(self) -> None:
        self._caller_identities = {
            participant.identity
            for participant in self._ctx.room.remote_participants.values()
            if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        }
        self._ctx.room.on("participant_disconnected", self._on_participant_disconnected)

    def _on_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        if participant.identity not in self._caller_identities and (
            participant.identity != self._front_desk_identity
        ):
            return
        if self._shutting_down:
            return
        self._shutting_down = True
        self._ctx.room.off("participant_disconnected", self._on_participant_disconnected)
        self._event("transfer_ended", participant=participant.identity)
        self._ctx.shutdown()

    def _set_io(self, enabled: bool) -> None:
        try:
            self._session.input.set_audio_enabled(enabled)
            self._session.output.set_audio_enabled(enabled)
        except Exception as exc:
            logger.warning("could not set agent audio state: %r", exc)

    def _event(self, event: str, **fields: Any) -> None:
        if self._on_event is not None:
            self._on_event(event, **fields)
