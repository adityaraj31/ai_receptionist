from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg
import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from alembic import command

API_DIR = Path(__file__).resolve().parents[1]

BASE_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://receptionist:receptionist_dev_password@localhost:5432/receptionist",
)
_base_url = make_url(BASE_DATABASE_URL)
TEST_DATABASE_NAME = os.environ.get("TEST_DB_NAME", f"{_base_url.database}_test")
TEST_DATABASE_URL = _base_url.set(database=TEST_DATABASE_NAME)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DASHBOARD_URL", "http://localhost:3000")

from app.core.passwords import hash_password  # noqa: E402
from app.core.security import create_access_token, hash_service_key  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AgentApiKey,
    Base,
    Clinic,
    Doctor,
    StaffUser,
)

TEST_AGENT_KEY = "test-agent-key"
KOLKATA = ZoneInfo("Asia/Kolkata")


async def _ensure_test_database() -> None:
    admin = TEST_DATABASE_URL.set(database="postgres")
    connection = await asyncpg.connect(
        user=admin.username,
        password=admin.password,
        host=admin.host,
        port=admin.port or 5432,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DATABASE_NAME
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{TEST_DATABASE_NAME}"')
    finally:
        await connection.close()


def _upgrade_to_head() -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> None:
    asyncio.run(_ensure_test_database())
    _upgrade_to_head()


@pytest_asyncio.fixture(autouse=True)
async def clean_database(setup_database: None):
    table_names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def clinic(db_session) -> Clinic:
    clinic = Clinic(
        name="Test Clinic",
        timezone="Asia/Kolkata",
        address="1 Test Street",
        phone="+91 90000 00000",
        email="clinic@test.test",
    )
    db_session.add(clinic)
    await db_session.commit()
    await db_session.refresh(clinic)
    return clinic


@pytest_asyncio.fixture
async def doctor(db_session, clinic) -> Doctor:
    doctor = Doctor(
        clinic_id=clinic.id,
        name="Dr. Test",
        specialization="General Medicine",
        languages=["English", "Hindi"],
        fee=Decimal("500.00"),
    )
    db_session.add(doctor)
    await db_session.commit()
    await db_session.refresh(doctor)
    return doctor


@pytest_asyncio.fixture
async def staff(db_session, clinic) -> StaffUser:
    staff = StaffUser(
        clinic_id=clinic.id,
        email="staff@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Test Staff",
        role="admin",
    )
    db_session.add(staff)
    await db_session.commit()
    await db_session.refresh(staff)
    return staff


@pytest_asyncio.fixture
async def auth_headers(staff) -> dict[str, str]:
    token, _ = create_access_token(staff.id, staff.clinic_id, staff.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def agent_headers(db_session, clinic) -> dict[str, str]:
    db_session.add(
        AgentApiKey(
            clinic_id=clinic.id,
            label="test-agent",
            key_hash=hash_service_key(TEST_AGENT_KEY),
        )
    )
    await db_session.commit()
    return {"X-Service-Key": TEST_AGENT_KEY}


@pytest_asyncio.fixture
async def other_doctor(db_session) -> Doctor:
    other_clinic = Clinic(name="Other Clinic", timezone="Asia/Kolkata")
    db_session.add(other_clinic)
    await db_session.flush()
    doctor = Doctor(
        clinic_id=other_clinic.id,
        name="Dr. Other",
        specialization="Cardiology",
        languages=["English"],
        fee=Decimal("900.00"),
    )
    db_session.add(doctor)
    await db_session.commit()
    await db_session.refresh(doctor)
    return doctor


@pytest.fixture
def next_weekday():
    def _next_weekday(iso_weekday: int) -> date:
        today = date.today()
        delta = (iso_weekday - today.isoweekday()) % 7
        if delta == 0:
            delta = 7
        return today + timedelta(days=delta + 7)

    return _next_weekday


@pytest.fixture
def at_time():
    def _at_time(day: date, hour: int = 9, minute: int = 0) -> datetime:
        return datetime.combine(day, time(hour, minute), tzinfo=KOLKATA)

    return _at_time
