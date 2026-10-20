from __future__ import annotations


async def test_update_clinic(client, auth_headers, clinic):
    response = await client.patch(
        "/api/v1/clinic",
        json={
            "name": "Updated Clinic",
            "timezone": "Asia/Dubai",
            "address": "2 New Street",
            "phone": "+91 91111 11111",
            "email": "hello@example.com",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(clinic.id)
    assert body["name"] == "Updated Clinic"
    assert body["timezone"] == "Asia/Dubai"
    assert body["address"] == "2 New Street"
    assert body["phone"] == "+91 91111 11111"
    assert body["email"] == "hello@example.com"


async def test_update_clinic_allows_partial_and_clearing(client, auth_headers, clinic):
    response = await client.patch(
        "/api/v1/clinic",
        json={"phone": None, "name": "  Renamed Clinic  "},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed Clinic"
    assert body["phone"] is None
    assert body["address"] == "1 Test Street"


async def test_update_clinic_rejects_invalid_values(client, auth_headers):
    blank = await client.patch(
        "/api/v1/clinic",
        json={"name": "   "},
        headers=auth_headers,
    )
    assert blank.status_code == 422

    timezone = await client.patch(
        "/api/v1/clinic",
        json={"timezone": "Mars/Olympus_Mons"},
        headers=auth_headers,
    )
    assert timezone.status_code == 422


async def test_update_clinic_requires_staff_auth(client, agent_headers):
    response = await client.patch(
        "/api/v1/clinic",
        json={"name": "No Auth Clinic"},
        headers=agent_headers,
    )
    assert response.status_code == 401
