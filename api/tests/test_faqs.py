from __future__ import annotations

from uuid import UUID

import pytest

from app.models import FaqChunk
from app.services import embeddings

DIMENSIONS = 384


def fake_vector(text: str) -> list[float]:
    lowered = text.lower()
    vector = [0.0] * DIMENSIONS
    if any(word in lowered for word in ("time", "hour", "open", "खुल", "बजे")):
        vector[0] = 1.0
    elif any(word in lowered for word in ("fee", "cost", "charge", "शुल्क", "फीस")):
        vector[1] = 1.0
    elif any(word in lowered for word in ("park", "address", "location", "पता", "पार्किंग")):
        vector[2] = 1.0
    else:
        vector[3] = 1.0
    return vector


async def fake_embed(texts: list[str]) -> list[list[float]]:
    return [fake_vector(text) for text in texts]


@pytest.fixture(autouse=True)
def patch_embeddings(monkeypatch):
    monkeypatch.setattr(embeddings, "aembed_documents", fake_embed)


async def test_create_list_update_and_deactivate_faq(client, auth_headers):
    created = await client.post(
        "/api/v1/faqs",
        json={
            "question": "What are your timings?",
            "answer": "We are open Monday to Saturday, 9 AM to 6 PM.",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    faq = created.json()
    assert faq["question"] == "What are your timings?"
    assert faq["is_active"] is True
    assert UUID(faq["id"])

    listed = await client.get("/api/v1/faqs", headers=auth_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [faq["id"]]

    updated = await client.patch(
        f"/api/v1/faqs/{faq['id']}",
        json={"answer": "We are open Monday to Saturday, 9 AM to 7 PM."},
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["answer"].endswith("7 PM.")

    deactivated = await client.delete(
        f"/api/v1/faqs/{faq['id']}",
        headers=auth_headers,
    )
    assert deactivated.status_code == 204

    active = await client.get("/api/v1/faqs", headers=auth_headers)
    assert active.json() == []

    all_faqs = await client.get(
        "/api/v1/faqs",
        params={"include_inactive": True},
        headers=auth_headers,
    )
    assert all_faqs.json()[0]["is_active"] is False


async def test_search_returns_two_sentence_answer(client, auth_headers, agent_headers):
    created = await client.post(
        "/api/v1/faqs",
        json={
            "question": "What are your timings?",
            "answer": (
                "We are open Monday to Saturday from 9 AM to 6 PM. "
                "Sunday is closed. Emergency care is available 24 hours."
            ),
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text

    response = await client.post(
        "/api/v1/agent/faq/search",
        json={"query": "What are your opening hours?"},
        headers=agent_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["found"] is True
    assert body["question"] == "What are your timings?"
    assert body["answer"] == ("We are open Monday to Saturday from 9 AM to 6 PM. Sunday is closed.")
    assert body["score"] > 0.99
    assert body["latency_ms"] >= 0


async def test_search_returns_not_found_below_threshold(client, auth_headers, agent_headers):
    await client.post(
        "/api/v1/faqs",
        json={
            "question": "What are your timings?",
            "answer": "We are open Monday to Saturday, 9 AM to 6 PM.",
        },
        headers=auth_headers,
    )

    response = await client.post(
        "/api/v1/agent/faq/search",
        json={"query": "Do you have parking?"},
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["found"] is False
    assert response.json()["answer"] is None


async def test_search_is_clinic_scoped(client, db_session, agent_headers, other_doctor):
    db_session.add(
        FaqChunk(
            clinic_id=other_doctor.clinic_id,
            question="Where can I park?",
            answer="Free parking is available in the basement.",
            content="Where can I park?\nFree parking is available in the basement.",
            chunk_index=0,
            embedding=fake_vector("parking"),
            is_active=True,
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/agent/faq/search",
        json={"query": "parking"},
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["found"] is False


async def test_faq_search_requires_service_key(client, auth_headers):
    response = await client.post(
        "/api/v1/agent/faq/search",
        json={"query": "timings"},
        headers=auth_headers,
    )
    assert response.status_code == 401


async def test_duplicate_question_is_rejected(client, auth_headers):
    payload = {
        "question": "Do you accept UPI?",
        "answer": "Yes, we accept UPI, cards, and cash.",
    }
    first = await client.post("/api/v1/faqs", json=payload, headers=auth_headers)
    assert first.status_code == 201

    duplicate = await client.post("/api/v1/faqs", json=payload, headers=auth_headers)
    assert duplicate.status_code == 409


async def test_rewording_keeps_faq_id(client, auth_headers):
    created = await client.post(
        "/api/v1/faqs",
        json={
            "question": "What are your timings?",
            "answer": "We are open Monday to Saturday, 9 AM to 6 PM.",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    faq_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/faqs/{faq_id}",
        json={
            "question": "What are the clinic timings and opening hours?",
            "is_active": False,
        },
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == faq_id
    assert updated.json()["is_active"] is False

    listed = await client.get(
        "/api/v1/faqs",
        params={"include_inactive": True},
        headers=auth_headers,
    )
    assert [item["id"] for item in listed.json()] == [faq_id]
    assert listed.json()[0]["question"] == "What are the clinic timings and opening hours?"
