from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.time import clinic_timezone, day_bounds
from ..models import Appointment, AvailabilityRule, Clinic, Doctor, TimeOff


@dataclass(frozen=True)
class FreeSlot:
    doctor_id: UUID
    slot_date: date
    starts_at: datetime
    ends_at: datetime
    slot_minutes: int
    timezone: str


async def get_free_slots(
    session: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    day: date,
    *,
    exclude_appointment_id: UUID | None = None,
    now: datetime | None = None,
) -> list[FreeSlot]:
    rules = list(
        (
            await session.scalars(
                select(AvailabilityRule)
                .where(
                    AvailabilityRule.doctor_id == doctor.id,
                    AvailabilityRule.weekday == day.isoweekday(),
                    AvailabilityRule.is_active.is_(True),
                )
                .order_by(AvailabilityRule.start_time)
            )
        ).all()
    )
    if not rules:
        return []

    tz = clinic_timezone(clinic)
    day_start, day_end = day_bounds(day, tz)

    time_off = list(
        (
            await session.scalars(
                select(TimeOff).where(
                    TimeOff.doctor_id == doctor.id,
                    TimeOff.starts_at < day_end,
                    TimeOff.ends_at > day_start,
                )
            )
        ).all()
    )

    appointments_statement = select(Appointment).where(
        Appointment.clinic_id == clinic.id,
        Appointment.doctor_id == doctor.id,
        Appointment.status != "cancelled",
        Appointment.starts_at < day_end,
        Appointment.ends_at > day_start,
    )
    if exclude_appointment_id is not None:
        appointments_statement = appointments_statement.where(
            Appointment.id != exclude_appointment_id
        )
    appointments = list((await session.scalars(appointments_statement)).all())

    busy = [(item.starts_at, item.ends_at) for item in time_off]
    busy.extend((item.starts_at, item.ends_at) for item in appointments)

    current_now = now or datetime.now(UTC)
    slots: list[FreeSlot] = []
    seen: set[datetime] = set()

    for rule in rules:
        delta = timedelta(minutes=rule.slot_minutes)
        current = datetime.combine(day, rule.start_time, tzinfo=tz)
        rule_end = datetime.combine(day, rule.end_time, tzinfo=tz)

        while current + delta <= rule_end:
            candidate_start = current
            candidate_end = current + delta
            start_utc = candidate_start.astimezone(UTC)

            overlaps = any(
                candidate_start < busy_end and candidate_end > busy_start
                for busy_start, busy_end in busy
            )
            if start_utc >= current_now and start_utc not in seen and not overlaps:
                seen.add(start_utc)
                slots.append(
                    FreeSlot(
                        doctor_id=doctor.id,
                        slot_date=day,
                        starts_at=candidate_start,
                        ends_at=candidate_end,
                        slot_minutes=rule.slot_minutes,
                        timezone=clinic.timezone,
                    )
                )
            current += delta

    return sorted(slots, key=lambda slot: slot.starts_at)
