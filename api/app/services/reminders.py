from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from ..config import settings
from ..db import SessionLocal
from ..queue import enqueue_reminder
from .messaging import (
    ReminderKind,
    load_appointment_for_message,
    send_reminder,
)

logger = logging.getLogger(__name__)

REMINDER_LEADS: tuple[tuple[ReminderKind, timedelta], ...] = (
    ("reminder_24h", timedelta(hours=24)),
    ("reminder_2h", timedelta(hours=2)),
)


def plan_reminders(
    starts_at: datetime,
    now: datetime,
) -> list[tuple[ReminderKind, datetime]]:
    plan: list[tuple[ReminderKind, datetime]] = []
    for kind, lead in REMINDER_LEADS:
        run_at = starts_at - lead
        if run_at > now:
            plan.append((kind, run_at))
    return plan


async def schedule_appointment_reminders(
    appointment_id: UUID,
    starts_at: datetime,
) -> None:
    if not settings.reminder_jobs_enabled:
        return
    for kind, run_at in plan_reminders(starts_at, datetime.now(UTC)):
        await enqueue_reminder(str(appointment_id), kind, run_at, starts_at)


async def send_appointment_reminder(
    _ctx: dict[str, Any],
    appointment_id: str,
    kind: str,
    expected_starts_at: str,
) -> dict[str, str]:
    if kind not in {"reminder_24h", "reminder_2h"}:
        return {"status": "skipped", "reason": "unknown_kind"}
    expected = datetime.fromisoformat(expected_starts_at)

    async with SessionLocal() as session:
        try:
            appointment = await load_appointment_for_message(session, UUID(appointment_id))
        except HTTPException:
            logger.warning("Reminder appointment not found: %s", appointment_id)
            return {"status": "skipped", "reason": "not_found"}

        if appointment.status != "booked":
            return {"status": "skipped", "reason": "not_booked"}
        if appointment.starts_at.astimezone(UTC) != expected.astimezone(UTC):
            return {"status": "skipped", "reason": "rescheduled"}

        log = await send_reminder(session, appointment, kind)  # type: ignore[arg-type]
        return {"status": log.status, "kind": kind, "log_id": str(log.id)}
