"""Seed one demo clinic, staff user, doctors, availability, and agent key.

Run from the api directory:
    uv run python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import select, update

API_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = API_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(API_DIR / ".env")
sys.path.insert(0, str(API_DIR))

from app.core.passwords import hash_password  # noqa: E402
from app.core.security import hash_service_key  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AgentApiKey,
    AvailabilityRule,
    Clinic,
    Doctor,
    StaffUser,
)


def required_secret(name: str, *, minimum_length: int) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is required. Add a strong value to .env before running the seed."
        )
    if len(value) < minimum_length:
        raise RuntimeError(f"{name} must be at least {minimum_length} characters.")
    return value


DEMO_EMAIL = os.getenv("DEMO_STAFF_EMAIL", "admin@demo-clinic.example.com")
DEMO_PASSWORD = required_secret("DEMO_STAFF_PASSWORD", minimum_length=12)
DEMO_AGENT_KEY = required_secret("DEMO_AGENT_KEY", minimum_length=24)

DOCTORS = [
    {
        "name": "Dr. Asha Rao",
        "specialization": "General Medicine",
        "languages": ["English", "Hindi"],
        "fee": "500.00",
        "rules": [
            (1, time(9, 0), time(13, 0), 15),
            (1, time(15, 0), time(18, 0), 15),
            (2, time(9, 0), time(13, 0), 15),
            (2, time(15, 0), time(18, 0), 15),
            (3, time(9, 0), time(13, 0), 15),
            (3, time(15, 0), time(18, 0), 15),
            (4, time(9, 0), time(13, 0), 15),
            (4, time(15, 0), time(18, 0), 15),
            (5, time(9, 0), time(13, 0), 15),
            (5, time(15, 0), time(18, 0), 15),
            (6, time(9, 0), time(12, 0), 15),
        ],
    },
    {
        "name": "Dr. Vikram Shah",
        "specialization": "Pediatrics",
        "languages": ["English", "Hindi", "Gujarati"],
        "fee": "600.00",
        "rules": [
            (1, time(10, 0), time(14, 0), 20),
            (2, time(10, 0), time(14, 0), 20),
            (3, time(10, 0), time(14, 0), 20),
            (4, time(10, 0), time(14, 0), 20),
            (5, time(10, 0), time(14, 0), 20),
            (6, time(10, 0), time(13, 0), 20),
        ],
    },
    {
        "name": "Dr. Meera Iyer",
        "specialization": "Dermatology",
        "languages": ["English", "Hindi", "Tamil"],
        "fee": "700.00",
        "rules": [
            (2, time(11, 0), time(17, 0), 30),
            (3, time(11, 0), time(17, 0), 30),
            (4, time(11, 0), time(17, 0), 30),
            (5, time(11, 0), time(17, 0), 30),
            (6, time(11, 0), time(17, 0), 30),
        ],
    },
]


async def get_or_create_clinic(session) -> Clinic:
    clinic = await session.scalar(select(Clinic).where(Clinic.name == "Demo Family Clinic"))
    if clinic is not None:
        clinic.is_active = True
        return clinic

    clinic = Clinic(
        name="Demo Family Clinic",
        timezone="Asia/Kolkata",
        address="12 MG Road, Bengaluru, Karnataka 560001",
        phone="+91 80 4000 1234",
        email="hello@demo-clinic.example.com",
    )
    session.add(clinic)
    await session.flush()
    return clinic


async def get_or_create_staff(session, clinic_id: UUID) -> StaffUser:
    staff = await session.scalar(select(StaffUser).where(StaffUser.email == DEMO_EMAIL))
    if staff is None:
        staff = StaffUser(
            clinic_id=clinic_id,
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Demo Admin",
            role="admin",
        )
        session.add(staff)
    else:
        staff.password_hash = hash_password(DEMO_PASSWORD)
        staff.is_active = True
    return staff


async def get_or_create_doctor(session, clinic_id: UUID, data: dict) -> Doctor:
    doctor = await session.scalar(
        select(Doctor).where(
            Doctor.clinic_id == clinic_id,
            Doctor.name == data["name"],
        )
    )
    if doctor is None:
        doctor = Doctor(
            clinic_id=clinic_id,
            name=data["name"],
            specialization=data["specialization"],
            languages=data["languages"],
            fee=Decimal(data["fee"]),
        )
        session.add(doctor)
        await session.flush()
    else:
        doctor.specialization = data["specialization"]
        doctor.languages = data["languages"]
        doctor.fee = Decimal(data["fee"])
        doctor.is_active = True
    return doctor


async def ensure_rule(
    session,
    doctor_id: UUID,
    weekday: int,
    start_time: time,
    end_time: time,
    slot_minutes: int,
) -> None:
    existing = await session.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.doctor_id == doctor_id,
            AvailabilityRule.weekday == weekday,
            AvailabilityRule.start_time == start_time,
            AvailabilityRule.end_time == end_time,
        )
    )
    if existing is None:
        session.add(
            AvailabilityRule(
                doctor_id=doctor_id,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                slot_minutes=slot_minutes,
            )
        )
    else:
        existing.slot_minutes = slot_minutes
        existing.is_active = True


async def ensure_agent_key(session, clinic_id: UUID) -> None:
    key_hash = hash_service_key(DEMO_AGENT_KEY)
    await session.execute(
        update(AgentApiKey)
        .where(
            AgentApiKey.clinic_id == clinic_id,
            AgentApiKey.label == "demo-agent",
            AgentApiKey.key_hash != key_hash,
        )
        .values(is_active=False)
    )

    existing = await session.scalar(select(AgentApiKey).where(AgentApiKey.key_hash == key_hash))
    if existing is None:
        session.add(
            AgentApiKey(
                clinic_id=clinic_id,
                label="demo-agent",
                key_hash=key_hash,
            )
        )
    else:
        existing.is_active = True
        existing.label = "demo-agent"


async def main() -> None:
    async with SessionLocal() as session:
        clinic = await get_or_create_clinic(session)
        await get_or_create_staff(session, clinic.id)

        for data in DOCTORS:
            doctor = await get_or_create_doctor(session, clinic.id, data)
            for weekday, start_time, end_time, slot_minutes in data["rules"]:
                await ensure_rule(session, doctor.id, weekday, start_time, end_time, slot_minutes)

        await ensure_agent_key(session, clinic.id)
        await session.commit()

    print("Demo clinic seeded.")
    print(f"Staff login email: {DEMO_EMAIL}")
    print("Staff password and agent key were read from DEMO_STAFF_PASSWORD and DEMO_AGENT_KEY.")


if __name__ == "__main__":
    asyncio.run(main())
