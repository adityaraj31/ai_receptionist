from __future__ import annotations

from datetime import time

from app.models import AvailabilityRule


async def test_agent_clinic_config_requires_service_key(
    client,
    db_session,
    doctor,
    auth_headers,
    agent_headers,
):
    anonymous = await client.get("/api/v1/agent/clinic-config")
    assert anonymous.status_code == 401

    staff = await client.get("/api/v1/agent/clinic-config", headers=auth_headers)
    assert staff.status_code == 401

    db_session.add(
        AvailabilityRule(
            doctor_id=doctor.id,
            weekday=1,
            start_time=time(9, 0),
            end_time=time(13, 0),
            slot_minutes=15,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/agent/clinic-config", headers=agent_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["clinic"]["id"] == str(doctor.clinic_id)
    assert body["clinic"]["name"] == "Test Clinic"
    assert [item["id"] for item in body["doctors"]] == [str(doctor.id)]
    assert body["doctors"][0]["specialization"] == "General Medicine"
    assert body["doctors"][0]["languages"] == ["English", "Hindi"]
    assert body["availability"] == [
        {
            "doctor_id": str(doctor.id),
            "weekday": 1,
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "slot_minutes": 15,
        }
    ]


async def test_agent_clinic_config_hides_inactive_doctors(
    client,
    db_session,
    doctor,
    agent_headers,
):
    doctor.is_active = False
    await db_session.commit()

    response = await client.get("/api/v1/agent/clinic-config", headers=agent_headers)
    assert response.status_code == 200
    assert response.json()["doctors"] == []
    assert response.json()["availability"] == []


async def test_agent_key_can_get_appointment_by_id(
    client,
    db_session,
    doctor,
    agent_headers,
    next_weekday,
    at_time,
):
    day = next_weekday(1)
    db_session.add(
        AvailabilityRule(
            doctor_id=doctor.id,
            weekday=day.isoweekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_minutes=15,
        )
    )
    await db_session.commit()

    created = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "starts_at": at_time(day, 9, 0).isoformat(),
            "ends_at": at_time(day, 9, 15).isoformat(),
            "patient_name": "Agent Lookup",
            "patient_phone": "+919888888888",
        },
        headers=agent_headers,
    )
    assert created.status_code == 201

    response = await client.get(
        f"/api/v1/appointments/{created.json()['id']}",
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["patient_name"] == "Agent Lookup"
