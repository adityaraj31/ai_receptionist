from __future__ import annotations

from uuid import UUID

import pytest

from app.models import CallbackTask


async def test_agent_creates_callback_task(client, clinic, agent_headers):
    response = await client.post(
        "/api/v1/agent/callbacks",
        json={
            "caller_name": "Ravi Kumar",
            "phone": "+91 90000 00000",
            "reason": "transfer_no_answer",
            "message": "Wants to speak about an insurance claim.",
        },
        headers=agent_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert UUID(body["id"])
    assert body["phone"] == "+919000000000"
    assert body["status"] == "pending"
    assert body["source"] == "agent"
    assert body["caller_name"] == "Ravi Kumar"


async def test_agent_callback_requires_service_key(client):
    response = await client.post(
        "/api/v1/agent/callbacks",
        json={"caller_name": "Ravi", "phone": "+919000000000"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("phone", ["123", "", "not-a-phone"])
async def test_agent_callback_rejects_invalid_phone(client, agent_headers, phone):
    response = await client.post(
        "/api/v1/agent/callbacks",
        json={"caller_name": "Ravi", "phone": phone},
        headers=agent_headers,
    )
    assert response.status_code == 422


async def test_staff_lists_and_updates_callbacks(client, db_session, clinic, auth_headers):
    db_session.add(
        CallbackTask(
            clinic_id=clinic.id,
            caller_name="Ravi Kumar",
            phone="+919000000000",
            reason="asks for a human",
            message="Call after 5 PM.",
        )
    )
    await db_session.commit()

    listed = await client.get("/api/v1/callbacks", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["caller_name"] == "Ravi Kumar"

    pending = await client.get(
        "/api/v1/callbacks",
        params={"status": "pending"},
        headers=auth_headers,
    )
    assert len(pending.json()) == 1

    updated = await client.patch(
        f"/api/v1/callbacks/{body[0]['id']}",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "done"

    done = await client.get(
        "/api/v1/callbacks",
        params={"status": "pending"},
        headers=auth_headers,
    )
    assert done.json() == []


async def test_callbacks_are_clinic_scoped(
    client,
    db_session,
    clinic,
    auth_headers,
    other_doctor,
):
    other = CallbackTask(
        clinic_id=other_doctor.clinic_id,
        caller_name="Other Caller",
        phone="+919111111111",
    )
    db_session.add(other)
    await db_session.commit()

    listed = await client.get("/api/v1/callbacks", headers=auth_headers)
    assert listed.json() == []

    updated = await client.patch(
        f"/api/v1/callbacks/{other.id}",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert updated.status_code == 404


async def test_clinic_front_desk_number_is_saved_and_served_to_agent(
    client,
    clinic,
    auth_headers,
    agent_headers,
):
    updated = await client.patch(
        "/api/v1/clinic",
        json={"front_desk_number": "+91 80690 00000"},
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["front_desk_number"] == "+918069000000"

    config = await client.get("/api/v1/agent/clinic-config", headers=agent_headers)
    assert config.status_code == 200
    assert config.json()["clinic"]["front_desk_number"] == "+918069000000"


async def test_clinic_front_desk_number_can_be_cleared(client, clinic, auth_headers):
    await client.patch(
        "/api/v1/clinic",
        json={"front_desk_number": "+918069000000"},
        headers=auth_headers,
    )
    cleared = await client.patch(
        "/api/v1/clinic",
        json={"front_desk_number": ""},
        headers=auth_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["front_desk_number"] is None
