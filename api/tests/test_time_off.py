from __future__ import annotations

from datetime import datetime


async def create_time_off(
    client,
    headers,
    doctor,
    starts_at: datetime,
    ends_at: datetime,
    *,
    reason: str = "Leave",
):
    return await client.post(
        f"/api/v1/doctors/{doctor.id}/time-off",
        json={
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "reason": reason,
        },
        headers=headers,
    )


async def test_time_off_create_list_update_and_delete(
    client, doctor, auth_headers, next_weekday, at_time
):
    day = next_weekday(2)
    created = await create_time_off(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 10, 0),
    )
    assert created.status_code == 201
    time_off_id = created.json()["id"]

    listed = await client.get(
        f"/api/v1/doctors/{doctor.id}/time-off",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = await client.patch(
        f"/api/v1/doctors/{doctor.id}/time-off/{time_off_id}",
        json={
            "ends_at": at_time(day, 10, 30).isoformat(),
            "reason": "Training",
        },
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["reason"] == "Training"
    assert datetime.fromisoformat(updated.json()["ends_at"]) == at_time(day, 10, 30)

    deleted = await client.delete(
        f"/api/v1/doctors/{doctor.id}/time-off/{time_off_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204

    after = await client.get(
        f"/api/v1/doctors/{doctor.id}/time-off",
        headers=auth_headers,
    )
    assert after.json() == []


async def test_overlapping_time_off_is_rejected(
    client, doctor, auth_headers, next_weekday, at_time
):
    day = next_weekday(2)
    first = await create_time_off(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 10, 0),
    )
    assert first.status_code == 201

    overlapping = await create_time_off(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 30),
        at_time(day, 10, 30),
    )
    assert overlapping.status_code == 409


async def test_time_off_update_rejects_overlap(client, doctor, auth_headers, next_weekday, at_time):
    day = next_weekday(2)
    first = await create_time_off(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 10, 0),
    )
    second = await create_time_off(
        client,
        auth_headers,
        doctor,
        at_time(day, 11, 0),
        at_time(day, 12, 0),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    response = await client.patch(
        f"/api/v1/doctors/{doctor.id}/time-off/{second.json()['id']}",
        json={
            "starts_at": at_time(day, 9, 30).isoformat(),
            "ends_at": at_time(day, 10, 30).isoformat(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 409


async def test_time_off_update_rejects_invalid_range(
    client, doctor, auth_headers, next_weekday, at_time
):
    day = next_weekday(2)
    created = await create_time_off(
        client,
        auth_headers,
        doctor,
        at_time(day, 9, 0),
        at_time(day, 10, 0),
    )

    response = await client.patch(
        f"/api/v1/doctors/{doctor.id}/time-off/{created.json()['id']}",
        json={"ends_at": at_time(day, 8, 30).isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 422
