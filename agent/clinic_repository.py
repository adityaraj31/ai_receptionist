"""Postgres-backed clinic configuration for the agent."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import time
from typing import Any
from uuid import UUID

import asyncpg

from prompts import ClinicConfig, Doctor

DAY_NAMES = (
    None,
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

DAY_ABBREVIATIONS = (
    None,
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
)

DB_CONNECT_TIMEOUT_SECONDS = 5.0
DB_COMMAND_TIMEOUT_SECONDS = 5.0


def normalize_dsn(database_url: str) -> str:
    """Accept SQLAlchemy-style URLs (postgresql+asyncpg://) as well as plain DSNs."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1).replace(
        "postgres+asyncpg://", "postgresql://", 1
    )


async def load_clinic_config_from_db(
    database_url: str,
    clinic_id: str | None = None,
) -> ClinicConfig | None:
    """Load the clinic, doctors, and availability from Postgres.

    If ``clinic_id`` is omitted, the first active clinic is used.
    Returns ``None`` when no matching clinic exists.
    """
    conn = await asyncpg.connect(
        normalize_dsn(database_url),
        timeout=DB_CONNECT_TIMEOUT_SECONDS,
        command_timeout=DB_COMMAND_TIMEOUT_SECONDS,
    )
    try:
        if clinic_id:
            clinic = await conn.fetchrow(
                """
                SELECT id, name, timezone, address, phone, front_desk_number
                FROM clinics
                WHERE id = $1::uuid AND is_active = TRUE
                """,
                clinic_id,
            )
        else:
            clinic = await conn.fetchrow(
                """
                SELECT id, name, timezone, address, phone, front_desk_number
                FROM clinics
                WHERE is_active = TRUE
                ORDER BY created_at
                LIMIT 1
                """
            )

        if clinic is None:
            return None

        doctors = await conn.fetch(
            """
            SELECT id, name, specialization
            FROM doctors
            WHERE clinic_id = $1 AND is_active = TRUE
            ORDER BY name
            """,
            clinic["id"],
        )

        doctor_ids = [row["id"] for row in doctors]
        if doctor_ids:
            rules = await conn.fetch(
                """
                SELECT doctor_id, weekday, start_time, end_time
                FROM availability_rules
                WHERE doctor_id = ANY($1::uuid[]) AND is_active = TRUE
                ORDER BY weekday, start_time
                """,
                doctor_ids,
            )
        else:
            rules = []

        return build_config_from_rows(
            dict(clinic),
            [dict(row) for row in doctors],
            [dict(row) for row in rules],
        )
    finally:
        await conn.close()


def _format_windows(rules: Sequence[Mapping[str, Any]]) -> str:
    windows = sorted(
        {
            f"{row['start_time'].strftime('%H:%M')}-{row['end_time'].strftime('%H:%M')}"
            for row in rules
            if isinstance(row.get("start_time"), time) and isinstance(row.get("end_time"), time)
        }
    )
    return ", ".join(windows)


def _coerce_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None
    return None


def _format_fee(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _format_days(weekdays: set[int]) -> str:
    return ", ".join(DAY_ABBREVIATIONS[weekday] for weekday in sorted(weekdays))


def _format_clinic_hours(rules: Sequence[Mapping[str, Any]]) -> str:
    starts = [row["start_time"] for row in rules if isinstance(row.get("start_time"), time)]
    ends = [row["end_time"] for row in rules if isinstance(row.get("end_time"), time)]
    if not starts or not ends:
        return ""
    return f"{min(starts).strftime('%H:%M')}-{max(ends).strftime('%H:%M')}"


def build_config_from_rows(
    clinic: Mapping[str, Any],
    doctors: Sequence[Mapping[str, Any]],
    rules: Sequence[Mapping[str, Any]],
) -> ClinicConfig:
    """Convert clinic, doctor, and availability rows into the prompt's ClinicConfig."""
    rules_by_doctor: dict[UUID, list[Mapping[str, Any]]] = defaultdict(list)
    rules_by_weekday: dict[int, list[Mapping[str, Any]]] = defaultdict(list)

    for row in rules:
        rules_by_doctor[row["doctor_id"]].append(row)
        rules_by_weekday[int(row["weekday"])].append(row)

    doctor_configs: list[Doctor] = []
    for row in doctors:
        doctor_rules = rules_by_doctor.get(row["id"], [])
        weekdays = {int(item["weekday"]) for item in doctor_rules}
        doctor_configs.append(
            Doctor(
                name=str(row["name"]),
                specialty=str(row.get("specialization") or ""),
                days=_format_days(weekdays),
                hours=_format_windows(doctor_rules),
                id=str(row["id"]),
                fee=_format_fee(row.get("fee")),
            )
        )

    timings: dict[str, str] = {}
    for weekday in range(1, 8):
        hours = _format_clinic_hours(rules_by_weekday.get(weekday, []))
        timings[DAY_NAMES[weekday]] = hours or "Closed"

    return ClinicConfig(
        name=str(clinic["name"]),
        doctors=tuple(doctor_configs),
        timings=timings,
        timezone=str(clinic.get("timezone") or "Asia/Kolkata"),
        address=str(clinic.get("address") or ""),
        phone=str(clinic.get("phone") or ""),
        front_desk_number=str(clinic.get("front_desk_number") or ""),
        fees=str(clinic.get("fees") or ""),
        emergency_number=str(clinic.get("emergency_number") or "108"),
    )


def build_config_from_api_payload(
    payload: Mapping[str, Any],
    fallback: ClinicConfig,
) -> ClinicConfig:
    """Convert the ``GET /api/v1/agent/clinic-config`` payload into a ClinicConfig.

    Non-clinic fields that the API does not store (fees, emergency number) come from
    the environment fallback.
    """
    clinic = payload.get("clinic") or {}
    doctors = payload.get("doctors") or []
    availability = payload.get("availability") or []

    rules: list[dict[str, Any]] = []
    for row in availability:
        start_time = _coerce_time(row.get("start_time"))
        end_time = _coerce_time(row.get("end_time"))
        if start_time is None or end_time is None:
            continue
        rules.append(
            {
                "doctor_id": row["doctor_id"],
                "weekday": int(row["weekday"]),
                "start_time": start_time,
                "end_time": end_time,
            }
        )

    config = build_config_from_rows(clinic, list(doctors), rules)
    return ClinicConfig(
        name=config.name,
        doctors=config.doctors,
        timings=config.timings,
        timezone=config.timezone,
        address=config.address or fallback.address,
        phone=config.phone or fallback.phone,
        front_desk_number=config.front_desk_number or fallback.front_desk_number,
        fees=fallback.fees,
        emergency_number=fallback.emergency_number,
    )
