import random
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from app.models.models import AgentDB, IncidentDB


def tick(db: Session) -> None:
    """Advance the world simulation by one step."""
    _auto_resolve_stale(db)
    _update_agents(db)
    db.commit()


def _auto_resolve_stale(db: Session) -> None:
    cutoff = datetime.fromtimestamp(datetime.now().timestamp() - 6 * 3600)
    stale = db.query(IncidentDB).filter(
        IncidentDB.status != "resolved",
        IncidentDB.timestamp < cutoff,
    ).all()
    for inc in stale:
        inc.status = "resolved"
        if inc.assigned_agent_id:
            agent = db.query(AgentDB).filter(AgentDB.id == inc.assigned_agent_id).first()
            if agent:
                agent.status = "available"
                agent.current_incident = None
                agent.decision = "Auto-resolved (stale)"
                agent.status_message = "Patrolling sector"
    if stale:
        logger.info("Auto-resolved {n} stale incidents", n=len(stale))


def _update_agents(db: Session) -> None:
    agents = db.query(AgentDB).all()
    for agent in agents:
        if agent.role == "reserve_unit" and agent.status == "available":
            if random.random() < 0.2:
                db.delete(agent)
                continue

        if agent.status == "available":
            agent.stress = max(0.0, agent.stress - 0.5)
            agent.fuel = max(0.0, agent.fuel - 0.05)
            agent.status_message = "Patrolling sector"
            if agent.fuel < 20.0:
                agent.status = "refueling"
                agent.status_message = "Low fuel - Returning to base"
            else:
                agent.lat += random.uniform(-0.0005, 0.0005)
                agent.lon += random.uniform(-0.0005, 0.0005)

        elif agent.status == "busy":
            agent.stress = min(100.0, agent.stress + 0.8)
            agent.fuel = max(0.0, agent.fuel - 0.2)
            agent.status_message = f"Responding to Incident #{agent.current_incident}"

        elif agent.status == "refueling":
            agent.fuel = min(100.0, agent.fuel + 5.0)
            agent.stress = max(0.0, agent.stress - 2.0)
            agent.status_message = "Refueling at station"
            if agent.fuel >= 99.0:
                agent.status = "available"
