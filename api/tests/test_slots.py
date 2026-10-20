from __future__ import annotations

from datetime import time

from app.models import AvailabilityRule


async def add_rule(
    db_session,
    doctor,
    day,
    *,
    start_time: time = time(9, 0),
    end_time: time = time(10, 0),
    slot_minutes: int = 15,
) -> AvailabilityRule:
    rule = AvailabilityRule(
        doctor_id=doctor.id,
        weekday=day.isoweekday(),
        start_time=start_time,
        end_time=end_time,
        slot_minutes=slot_minutes,
    )
    db_session.add(rule)
    await db_session.commit()
    return rule


async def test_free_slots_are_generated_from_availability(
    client, db_session, doctor, auth_headers, next_weekday
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    response = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) == 4
    assert slots[0]["starts_at"].startswith(f"{day.isoformat()}T09:00:00")
    assert slots[-1]["starts_at"].startswith(f"{day.isoformat()}T09:45:00")
    assert slots[0]["slot_minutes"] == 15
    assert slots[0]["timezone"] == "Asia/Kolkata"


async def test_no_slots_on_day_without_availability(client, doctor, auth_headers, next_weekday):
    day = next_weekday(3)
    response = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_time_off_removes_only_overlapping_slots(
    client, db_session, doctor, auth_headers, agent_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    response = await client.post(
        f"/api/v1/doctors/{doctor.id}/time-off",
        json={
            "starts_at": at_time(day, 9, 15).isoformat(),
            "ends_at": at_time(day, 9, 30).isoformat(),
            "reason": "Break",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    slots = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=agent_headers,
    )
    assert slots.status_code == 200
    starts = [slot["starts_at"][11:16] for slot in slots.json()]
    assert starts == ["09:00", "09:30", "09:45"]


async def test_full_time_off_removes_all_slots(
    client, db_session, doctor, auth_headers, next_weekday, at_time
):
    day = next_weekday(1)
    await add_rule(db_session, doctor, day)

    response = await client.post(
        f"/api/v1/doctors/{doctor.id}/time-off",
        json={
            "starts_at": at_time(day, 9, 0).isoformat(),
            "ends_at": at_time(day, 10, 0).isoformat(),
            "reason": "Leave",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    slots = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=auth_headers,
    )
    assert slots.json() == []


async def test_agent_can_read_free_slots(client, db_session, doctor, agent_headers, next_weekday):
    day = next_weekday(2)
    await add_rule(db_session, doctor, day, start_time=time(11, 0), end_time=time(12, 0))

    response = await client.get(
        f"/api/v1/doctors/{doctor.id}/free-slots?date={day.isoformat()}",
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert len(response.json()) == 4
