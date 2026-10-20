from datetime import time
from uuid import UUID

from clinic_repository import build_config_from_rows, normalize_dsn

DOCTOR_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_build_config_from_rows() -> None:
    clinic = {
        "name": "DB Clinic",
        "timezone": "Asia/Kolkata",
        "address": None,
        "phone": "+91 98765 43210",
    }
    doctors = [
        {
            "id": DOCTOR_ID,
            "name": "Dr. Meera Iyer",
            "specialization": "Family Medicine",
        }
    ]
    rules = [
        {
            "doctor_id": DOCTOR_ID,
            "weekday": 1,
            "start_time": time(9, 0),
            "end_time": time(13, 0),
        },
        {
            "doctor_id": DOCTOR_ID,
            "weekday": 1,
            "start_time": time(15, 0),
            "end_time": time(18, 0),
        },
        {
            "doctor_id": DOCTOR_ID,
            "weekday": 3,
            "start_time": time(9, 0),
            "end_time": time(13, 0),
        },
        {
            "doctor_id": DOCTOR_ID,
            "weekday": 3,
            "start_time": time(15, 0),
            "end_time": time(18, 0),
        },
    ]

    config = build_config_from_rows(clinic, doctors, rules)

    assert config.name == "DB Clinic"
    assert config.doctors[0].name == "Dr. Meera Iyer"
    assert config.doctors[0].specialty == "Family Medicine"
    assert config.doctors[0].days == "Mon, Wed"
    assert config.doctors[0].hours == "09:00-13:00, 15:00-18:00"
    assert config.timings["Monday"] == "09:00-18:00"
    assert config.timings["Sunday"] == "Closed"
    assert config.address == ""
    assert config.phone == "+91 98765 43210"
    assert config.emergency_number == "108"


def test_normalize_dsn_accepts_sqlalchemy_url() -> None:
    expected = "postgresql://user:pass@localhost:5432/receptionist"

    assert normalize_dsn("postgresql+asyncpg://user:pass@localhost:5432/receptionist") == expected
    assert normalize_dsn(expected) == expected
