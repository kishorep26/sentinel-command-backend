from app.models.models import AgentDB


def _seed_agent(db, name="Test Agent", atype="fire"):
    agent = AgentDB(
        name=name, type=atype, icon="🚒",
        status="available", lat=40.78, lon=-73.97,
        fuel=100.0, stress=0.0, role="standard",
    )
    db.add(agent)
    db.commit()
    return agent


def test_get_agents_returns_seeded_on_startup(client):
    # Lifespan seeds 6 default agents (2 fire, 2 police, 2 medical)
    resp = client.get("/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 6
    types = {a["type"] for a in agents}
    assert types == {"fire", "police", "medical"}


def test_get_agents_extra_agent(client, db):
    _seed_agent(db, "Special Unit 99", "medical")
    resp = client.get("/agents")
    assert resp.status_code == 200
    agents = resp.json()
    names = {a["name"] for a in agents}
    assert "Special Unit 99" in names


def test_simulation_tick_updates_agent_fuel(db):
    from app.services.simulation import tick
    agent = _seed_agent(db)
    tick(db)
    db.refresh(agent)
    assert agent.fuel < 100.0


def test_simulation_tick_refueling_agent(db):
    from app.services.simulation import tick
    agent = _seed_agent(db)
    agent.fuel = 15.0
    agent.status = "available"
    db.commit()
    tick(db)
    db.refresh(agent)
    assert agent.status == "refueling"


def test_simulation_busy_agent_gains_stress(db):
    from app.services.simulation import tick
    from app.models.models import IncidentDB
    from datetime import datetime

    inc = IncidentDB(type="fire", lat=40.78, lon=-73.97, description="test", status="active", timestamp=datetime.now(), created_at=datetime.now())
    db.add(inc)
    db.flush()

    agent = AgentDB(
        name="Busy Agent", type="fire", icon="🚒",
        status="busy", lat=40.78, lon=-73.97,
        fuel=80.0, stress=10.0, role="standard",
        current_incident=str(inc.id),
    )
    db.add(agent)
    db.commit()

    tick(db)
    db.refresh(agent)
    assert agent.stress > 10.0
    assert agent.fuel < 80.0
