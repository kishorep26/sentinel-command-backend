from datetime import datetime
from app.models.models import IncidentDB, AgentDB


def _seed_incidents(db, n=10):
    for i in range(n):
        db.add(IncidentDB(
            type="fire", lat=40.7 + i * 0.01, lon=-73.9 + i * 0.01,
            description=f"Incident {i}", status="active",
            timestamp=datetime.now(), created_at=datetime.now(),
        ))
    db.commit()


def test_stats_empty(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_incidents"] == 0
    assert body["active_incidents"] == 0


def test_stats_with_data(client, db):
    _seed_incidents(db, 3)
    resp = client.get("/stats")
    assert resp.status_code == 200
    assert resp.json()["total_incidents"] == 3


def test_incident_history_empty(client):
    resp = client.get("/incident-history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_prediction_insufficient_data(client, db):
    _seed_incidents(db, 3)
    resp = client.get("/analytics/prediction")
    assert resp.status_code == 200
    assert resp.json()["status"] == "insufficient_data"


def test_prediction_with_enough_data(client, db):
    _seed_incidents(db, 10)
    resp = client.get("/analytics/prediction")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert len(body["zones"]) > 0
