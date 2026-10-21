"""Send a test confirmation or reminder for an existing appointment.

Run from the api directory:
    uv run python -m scripts.test_messaging confirmation
    uv run python -m scripts.test_messaging confirmation --channel sms
    uv run python -m scripts.test_messaging reminder --kind reminder_2h

The script uses the demo clinic's agent key and the most recent booked
appointment, or pass ``--appointment-id``. With ``WHATSAPP_PROVIDER=fake`` and
``SMS_PROVIDER=fake`` the rendered message is logged and no real message is sent.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import UUID

import httpx
from dotenv import load_dotenv
from sqlalchemy import select

API_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = API_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(API_DIR / ".env")
sys.path.insert(0, str(API_DIR))

from app.core.security import hash_service_key  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import AgentApiKey, Appointment, MessageLog  # noqa: E402
from app.services.reminders import send_appointment_reminder  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["confirmation", "reminder"])
    parser.add_argument("--appointment-id", type=UUID)
    parser.add_argument("--channel", choices=["whatsapp", "sms"], default="whatsapp")
    parser.add_argument(
        "--reminder-kind",
        choices=["reminder_24h", "reminder_2h"],
        default="reminder_2h",
    )
    return parser.parse_args()


def agent_key() -> str:
    key = (os.getenv("AGENT_API_KEY") or os.getenv("DEMO_AGENT_KEY") or "").strip()
    if not key:
        raise SystemExit("Set AGENT_API_KEY or DEMO_AGENT_KEY in .env")
    return key


async def find_appointment(appointment_id: UUID | None) -> Appointment:
    key = agent_key()
    async with SessionLocal() as session:
        api_key = await session.scalar(
            select(AgentApiKey).where(
                AgentApiKey.key_hash == hash_service_key(key),
                AgentApiKey.is_active.is_(True),
            )
        )
        if api_key is None:
            raise SystemExit("The configured agent key does not match an active key")

        if appointment_id is not None:
            appointment = await session.get(Appointment, appointment_id)
            if appointment is None or appointment.clinic_id != api_key.clinic_id:
                raise SystemExit("Appointment not found for this clinic")
            return appointment

        appointment = await session.scalar(
            select(Appointment)
            .where(
                Appointment.clinic_id == api_key.clinic_id,
                Appointment.status == "booked",
            )
            .order_by(Appointment.starts_at.desc())
            .limit(1)
        )
        if appointment is None:
            raise SystemExit("No booked appointment. Book one in the dashboard first.")
        return appointment


async def latest_log(appointment_id: UUID, kind: str) -> MessageLog | None:
    async with SessionLocal() as session:
        return await session.scalar(
            select(MessageLog)
            .where(
                MessageLog.appointment_id == appointment_id,
                MessageLog.kind == kind,
            )
            .order_by(MessageLog.created_at.desc())
            .limit(1)
        )


async def send_confirmation(appointment: Appointment, channel: str) -> None:
    base_url = (os.getenv("AGENT_API_URL") or "http://localhost:8000").rstrip("/")
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        response = await client.post(
            f"/api/v1/agent/appointments/{appointment.id}/confirmation",
            json={"channel": channel},
            headers={"X-Service-Key": agent_key()},
        )
    print(response.status_code, response.json())


async def send_reminder(appointment: Appointment, kind: str) -> None:
    result = await send_appointment_reminder(
        {},
        str(appointment.id),
        kind,
        appointment.starts_at.isoformat(),
    )
    print(result)


async def main() -> None:
    args = parse_args()
    appointment = await find_appointment(args.appointment_id)
    print("appointment", appointment.id, appointment.starts_at.isoformat())

    if args.kind == "confirmation":
        await send_confirmation(appointment, args.channel)
        log_kind = "confirmation"
    else:
        await send_reminder(appointment, args.reminder_kind)
        log_kind = args.reminder_kind

    log = await latest_log(appointment.id, log_kind)
    if log is not None:
        print(
            "latest log:",
            log.status,
            log.provider,
            log.provider_message_id or "",
            log.error,
        )


if __name__ == "__main__":
    asyncio.run(main())
