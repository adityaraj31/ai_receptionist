from __future__ import annotations

from datetime import time
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Appointment, AvailabilityRule, Patient


async def add_rule(db_session, doctor, day, *, start=time(9, 0), end=time(10, 0)):
    db_session.add(
        AvailabilityRule(
            doctor_id=doctor.id,
            weekday=day.isoweekday(),
            start_time=start,
            end_time=end,
            slot_minutes=15,
        )
    )
    await db_session.commit()


async def book(
    client,
    headers,
    doctor,
    starts_at,
    ends_at,
    *,
    name: str = "Ravi Kumar",
    phone: str = "+919999999999",
):
    return await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "patient_name": name,
            "patient_phone": phone,
        },
        headers=headers,
    )


async def test_agent_can_book_an_appointment(
    client, db_session, doctor, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    response = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["source"] == "agent"
    assert body["patient_name"] == "Ravi Kumar"
    assert body["doctor_name"] == doctor.name


async def test_staff_booking_is_marked_as_staff(
    client, db_session, doctor, auth_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    response = await book(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    assert response.status_code == 201
    assert response.json()["source"] == "staff"


async def test_double_booking_same_slot_is_rejected(
    client, db_session, doctor, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    first = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
        phone="+919999999991",
    )
    assert first.status_code == 201

    second = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
        phone="+919999999992",
    )
    assert second.status_code == 409

    count = await db_session.scalar(select(func.count()).select_from(Appointment))
    assert count == 1


async def test_unaligned_or_overlapping_interval_is_rejected(
    client, db_session, doctor, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    first = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    assert first.status_code == 201

    overlapping = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 30),
        phone="+919999999993",
    )
    assert overlapping.status_code == 409


async def test_cancelled_slot_becomes_available_again(
    client, db_session, doctor, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    created = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    assert created.status_code == 201
    appointment_id = created.json()["id"]

    slots = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=agent_headers,
    )
    assert len(slots.json()) == 3

    cancelled = await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        headers=agent_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    slots_after = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=agent_headers,
    )
    assert len(slots_after.json()) == 4

    rebooked = await book(
        client,
        agent_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
        phone="+919999999994",
    )
    assert rebooked.status_code == 201


async def test_reschedule_moves_the_appointment(
    client, db_session, doctor, auth_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    created = await book(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 9, 15),
    )
    appointment_id = created.json()["id"]

    moved = await client.patch(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={
            "starts_at": at_time(day, 9, 15).isoformat(),
            "ends_at": at_time(day, 9, 30).isoformat(),
        },
        headers=auth_headers,
    )
    assert moved.status_code == 200
    assert moved.json()["starts_at"].startswith(f"{day.isoformat()}T09:15:00")

    slots = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=auth_headers,
    )
    starts = [slot["starts_at"][11:16] for slot in slots.json()]
    assert starts == ["09:00", "09:30", "09:45"]


async def test_list_appointments_by_day_and_doctor(
    client, db_session, doctor, auth_headers, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    for minute, phone in ((0, "+919999999995"), (15, "+919999999996")):
        response = await book(
            client,
            agent_headers,
            doctor,
            at_time(day, 9, minute),
            at_time(day, 9, minute + 15),
            phone=phone,
        )
        assert response.status_code == 201

    response = await client.get(
        f"/api/v1/appointments?date={day.isoformat()}&doctor_id={doctor.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    appointments = response.json()
    assert len(appointments) == 2
    assert appointments[0]["starts_at"] < appointments[1]["starts_at"]
    assert all(item["status"] == "booked" for item in appointments)


async def test_same_patient_phone_is_reused(
    client, db_session, doctor, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    for minute in (0, 15):
        response = await book(
            client,
            agent_headers,
            doctor,
            at_time(day, 9, minute),
            at_time(day, 9, minute + 15),
            phone="+919999999997",
        )
        assert response.status_code == 201

    count = await db_session.scalar(select(func.count()).select_from(Patient))
    assert count == 1


async def test_database_exclusion_constraint_blocks_overlaps(
    db_session, clinic, doctor, next_weekday, at_time
):
    day = next_weekday(1)
    patient = Patient(
        clinic_id=clinic.id,
        name="Direct Patient",
        phone=f"+919999{uuid4().int % 1000000:06d}",
    )
    db_session.add(patient)
    await db_session.flush()

    db_session.add(
        Appointment(
            clinic_id=clinic.id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            starts_at=at_time(day, 9, 0),
            ends_at=at_time(day, 9, 30),
            status="booked",
            source="staff",
        )
    )
    await db_session.flush()

    db_session.add(
        Appointment(
            clinic_id=clinic.id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            starts_at=at_time(day, 9, 15),
            ends_at=at_time(day, 9, 45),
            status="booked",
            source="staff",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()
