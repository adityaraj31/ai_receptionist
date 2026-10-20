from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.passwords import hash_password
from app.core.security import create_access_token
from app.models import StaffInvitation, StaffUser


async def _add_staff(
    db_session,
    clinic,
    email: str,
    *,
    role: str = "staff",
    is_active: bool = True,
) -> StaffUser:
    member = StaffUser(
        clinic_id=clinic.id,
        email=email,
        password_hash=hash_password("TestPassword123!"),
        full_name="Another Staff",
        role=role,
        is_active=is_active,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member


def _headers(member: StaffUser) -> dict[str, str]:
    token, _ = create_access_token(member.id, member.clinic_id, member.role)
    return {"Authorization": f"Bearer {token}"}


async def _invite(client, auth_headers, email: str = "new@example.com"):
    return await client.post(
        "/api/v1/staff/invitations",
        json={
            "email": email,
            "full_name": "New Receptionist",
            "role": "staff",
        },
        headers=auth_headers,
    )


async def test_admin_can_invite_and_new_staff_can_accept(
    client,
    auth_headers,
    clinic,
):
    created = await _invite(client, auth_headers, "New@Example.com")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "staff"
    assert body["invite_url"].startswith("http://localhost:3000/accept-invite/")
    token = body["invite_url"].rsplit("/", 1)[-1]

    pending = await client.get("/api/v1/staff/invitations", headers=auth_headers)
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()] == [body["id"]]

    preview = await client.get(f"/api/v1/invitations/{token}")
    assert preview.status_code == 200
    assert preview.json() == {
        "clinic_name": clinic.name,
        "email": "new@example.com",
        "full_name": "New Receptionist",
        "role": "staff",
        "expires_at": body["expires_at"],
    }

    accepted = await client.post(
        f"/api/v1/invitations/{token}/accept",
        json={"password": "BrandNewPassword123!"},
    )
    assert accepted.status_code == 200, accepted.text
    accepted_body = accepted.json()
    assert accepted_body["staff"]["email"] == "new@example.com"
    assert accepted_body["staff"]["clinic_id"] == str(clinic.id)

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "new@example.com", "password": "BrandNewPassword123!"},
    )
    assert login.status_code == 200

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {accepted_body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == accepted_body["staff"]["id"]

    reused = await client.post(
        f"/api/v1/invitations/{token}/accept",
        json={"password": "BrandNewPassword123!"},
    )
    assert reused.status_code == 404


async def test_invitation_preview_rejects_invalid_token(client):
    response = await client.get("/api/v1/invitations/not-a-real-token")
    assert response.status_code == 404


async def test_invitation_accept_validates_password(client, auth_headers):
    created = await _invite(client, auth_headers)
    token = created.json()["invite_url"].rsplit("/", 1)[-1]

    response = await client.post(
        f"/api/v1/invitations/{token}/accept",
        json={"password": "short"},
    )
    assert response.status_code == 422


async def test_invitation_cannot_duplicate_existing_or_pending_email(
    client,
    auth_headers,
    staff,
    db_session,
    clinic,
):
    existing = await _invite(client, auth_headers, staff.email.upper())
    assert existing.status_code == 409

    first = await _invite(client, auth_headers, "pending@example.com")
    assert first.status_code == 201
    second = await _invite(client, auth_headers, "PENDING@example.com")
    assert second.status_code == 409

    await _add_staff(db_session, clinic, "inactive@example.com", is_active=False)
    inactive = await _invite(client, auth_headers, "inactive@example.com")
    assert inactive.status_code == 409


async def test_expired_and_revoked_invitations_cannot_be_used(
    client,
    auth_headers,
    db_session,
):
    expired = await _invite(client, auth_headers, "expired@example.com")
    expired_token = expired.json()["invite_url"].rsplit("/", 1)[-1]
    invitation = await db_session.get(StaffInvitation, expired.json()["id"])
    invitation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    preview = await client.get(f"/api/v1/invitations/{expired_token}")
    assert preview.status_code == 404
    accepted = await client.post(
        f"/api/v1/invitations/{expired_token}/accept",
        json={"password": "BrandNewPassword123!"},
    )
    assert accepted.status_code == 404

    revoked = await _invite(client, auth_headers, "revoked@example.com")
    revoked_token = revoked.json()["invite_url"].rsplit("/", 1)[-1]
    response = await client.delete(
        f"/api/v1/staff/invitations/{revoked.json()['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    preview = await client.get(f"/api/v1/invitations/{revoked_token}")
    assert preview.status_code == 404


async def test_staff_management_requires_admin(
    client,
    db_session,
    clinic,
):
    member = await _add_staff(db_session, clinic, "member@example.com", role="staff")
    headers = _headers(member)

    listing = await client.get("/api/v1/staff", headers=headers)
    assert listing.status_code == 403
    created = await _invite(client, headers)
    assert created.status_code == 403
    pending = await client.get("/api/v1/staff/invitations", headers=headers)
    assert pending.status_code == 403


async def test_admin_can_deactivate_staff_and_existing_token_stops_working(
    client,
    auth_headers,
    db_session,
    clinic,
):
    member = await _add_staff(db_session, clinic, "member@example.com", role="staff")
    member_headers = _headers(member)

    updated = await client.patch(
        f"/api/v1/staff/{member.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "TestPassword123!"},
    )
    assert login.status_code == 401

    me = await client.get("/api/v1/auth/me", headers=member_headers)
    assert me.status_code == 401

    reactivated = await client.patch(
        f"/api/v1/staff/{member.id}",
        json={"is_active": True, "role": "admin", "full_name": "Promoted Staff"},
        headers=auth_headers,
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["role"] == "admin"
    assert reactivated.json()["full_name"] == "Promoted Staff"


async def test_null_staff_updates_are_ignored(client, auth_headers, staff):
    response = await client.patch(
        f"/api/v1/staff/{staff.id}",
        json={"full_name": None, "role": None, "is_active": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == staff.full_name
    assert response.json()["role"] == "admin"
    assert response.json()["is_active"] is True


async def test_admin_cannot_remove_own_admin_access(client, auth_headers, staff):
    deactivate = await client.patch(
        f"/api/v1/staff/{staff.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert deactivate.status_code == 400

    demote = await client.patch(
        f"/api/v1/staff/{staff.id}",
        json={"role": "staff"},
        headers=auth_headers,
    )
    assert demote.status_code == 400


async def test_staff_routes_are_clinic_scoped(
    client,
    auth_headers,
    db_session,
):
    from app.models import Clinic

    other_clinic = Clinic(name="Other Clinic", timezone="Asia/Kolkata")
    db_session.add(other_clinic)
    await db_session.flush()
    other_member = await _add_staff(db_session, other_clinic, "other@example.com")

    listing = await client.get("/api/v1/staff", headers=auth_headers)
    assert listing.status_code == 200
    assert str(other_member.id) not in {item["id"] for item in listing.json()}

    update = await client.patch(
        f"/api/v1/staff/{other_member.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert update.status_code == 404


async def test_openapi_documents_staff_and_invitation_routes(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "get" in paths["/api/v1/staff"]
    assert "patch" in paths["/api/v1/staff/{staff_id}"]
    assert "post" in paths["/api/v1/staff/invitations"]
    assert "get" in paths["/api/v1/invitations/{token}"]
    assert "post" in paths["/api/v1/invitations/{token}/accept"]
