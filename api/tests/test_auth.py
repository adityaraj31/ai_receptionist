from __future__ import annotations


async def test_login_and_me(client, staff):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": staff.email.upper(), "password": "TestPassword123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["staff"]["id"] == str(staff.id)

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == staff.email


async def test_login_rejects_bad_password(client, staff):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": staff.email, "password": "wrong"},
    )
    assert response.status_code == 401


async def test_protected_routes_require_auth(client):
    response = await client.get("/api/v1/doctors")
    assert response.status_code == 401


async def test_get_clinic_is_scoped_to_staff(client, auth_headers, clinic):
    response = await client.get("/api/v1/clinic", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(clinic.id)
    assert response.json()["timezone"] == "Asia/Kolkata"


async def test_agent_key_cannot_use_staff_routes(client, agent_headers):
    response = await client.get("/api/v1/doctors", headers=agent_headers)
    assert response.status_code == 401


async def test_staff_is_scoped_to_own_clinic(client, auth_headers, doctor, other_doctor):
    own = await client.get(f"/api/v1/doctors/{doctor.id}", headers=auth_headers)
    assert own.status_code == 200

    other = await client.get(f"/api/v1/doctors/{other_doctor.id}", headers=auth_headers)
    assert other.status_code == 404

    slots = await client.get(
        f"/api/v1/doctors/{other_doctor.id}/free-slots?date=2026-10-21",
        headers=auth_headers,
    )
    assert slots.status_code == 404


async def test_openapi_documents_auth_and_time_off_update(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200

    document = response.json()
    assert {"BearerAuth", "ServiceKeyAuth"} <= set(document["components"]["securitySchemes"])
    assert "patch" in document["paths"]["/api/v1/doctors/{doctor_id}/time-off/{time_off_id}"]


async def test_availability_overlap_is_rejected(client, auth_headers, doctor):
    first = await client.post(
        f"/api/v1/doctors/{doctor.id}/availability",
        json={
            "weekday": 1,
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "slot_minutes": 15,
        },
        headers=auth_headers,
    )
    assert first.status_code == 201

    overlap = await client.post(
        f"/api/v1/doctors/{doctor.id}/availability",
        json={
            "weekday": 1,
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "slot_minutes": 15,
        },
        headers=auth_headers,
    )
    assert overlap.status_code == 409
