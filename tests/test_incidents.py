from unittest.mock import patch
from tests.conftest import AUTH_HEADERS
from app.models.models import AgentDB


def _seed_agent(db, atype="fire"):
    agent = AgentDB(
        name=f"Test {atype.title()} 1",
        type=atype,
        icon="🚒",
        status="available",
        lat=40.78,
        lon=-73.97,
        fuel=100.0,
        stress=0.0,
        role="standard",
    )
    db.add(agent)
    db.commit()
    return agent


def test_get_incidents_empty(client):
    resp = client.get("/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_incident_requires_api_key(client):
    resp = client.post("/incidents", json={
        "type": "fire",
        "location": {"lat": 40.78, "lon": -73.97},
        "description": "Building on fire",
    })
    assert resp.status_code == 403


def test_create_incident_with_known_type(client, db):
    _seed_agent(db, "fire")
    resp = client.post(
        "/incidents",
        json={"type": "fire", "location": {"lat": 40.78, "lon": -73.97}, "description": "Fire on 5th Ave"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "fire"
    assert body["status"] == "active"


def test_create_incident_auto_type_uses_keyword_fallback(client, db):
    _seed_agent(db, "fire")
    with patch("app.services.ai.ai_classify", return_value=("fire", "Blaze detected (Severity: 8)")):
        resp = client.post(
            "/incidents",
            json={"type": "auto", "location": {"lat": 40.78, "lon": -73.97}, "description": "blaze on rooftop"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["type"] == "fire"


def test_resolve_incident(client, db):
    _seed_agent(db, "police")
    create_resp = client.post(
        "/incidents",
        json={"type": "police", "location": {"lat": 40.78, "lon": -73.97}, "description": "Fight in the park"},
        headers=AUTH_HEADERS,
    )
    incident_id = create_resp.json()["id"]

    resolve_resp = client.put(f"/incidents/{incident_id}/resolve", headers=AUTH_HEADERS)
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"


def test_resolve_nonexistent_incident(client):
    resp = client.put("/incidents/99999/resolve", headers=AUTH_HEADERS)
    assert resp.status_code == 404
