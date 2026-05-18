import math
import random
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from app.models.models import AgentDB, IncidentDB, IncidentHistoryDB, StatsDB

INCIDENT_TYPE_MAP: dict[str, str] = {
    "fire": "fire",
    "medical": "medical",
    "crime": "police",
    "accident": "police",
    "theft": "police",
    "robbery": "police",
    "assault": "police",
    "emergency": "medical",
    "hazard": "fire",
    "other": "police",
}

AGENT_ICONS = {"fire": "🚒", "medical": "🚑", "police": "🚓"}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def assign_agent(incident: IncidentDB, db: Session) -> AgentDB | None:
    preferred_type = INCIDENT_TYPE_MAP.get(incident.type.lower(), "police")

    available = db.query(AgentDB).filter(
        AgentDB.status == "available",
        AgentDB.type == preferred_type,
    ).all()

    if not available:
        logger.warning("No {t} units available — activating reserve", t=preferred_type)
        reserve = AgentDB(
            name=f"Reserve {preferred_type.title()} {random.randint(100, 999)}",
            type=preferred_type,
            icon=AGENT_ICONS.get(preferred_type, "🚨"),
            status="available",
            lat=incident.lat + random.uniform(-0.01, 0.01),
            lon=incident.lon + random.uniform(-0.01, 0.01),
            fuel=100.0,
            stress=0.0,
            role="reserve_unit",
            status_message="Activated from Reserve",
        )
        db.add(reserve)
        db.flush()
        available = [reserve]

    candidates = [
        (haversine(incident.lat, incident.lon, a.lat, a.lon), a)
        for a in available
    ]
    candidates.sort(key=lambda x: x[0] + x[1].stress * 0.05 + (100 - x[1].fuel) * 0.05)
    distance, agent = candidates[0]

    urgency = "HIGH" if incident.type in ("fire", "crime") else "MED"
    reason = (
        "RESERVE_ACTIVATION" if agent.role == "reserve_unit"
        else "STRESSED_ASSIGNMENT" if agent.stress > 60
        else "OPTIMAL"
    )
    decision_log = f"Sector Deployment | {agent.name} | PRIORITY:{urgency} | {reason}"

    incident.assigned_agent_id = agent.id
    agent.status = "busy"
    agent.current_incident = str(incident.id)
    agent.decision = decision_log
    agent.response_time = distance * 2
    agent.total_responses += 1
    agent.updated_at = datetime.now()
    agent.status_message = f"Responding to Incident #{incident.id}"

    db.add(IncidentHistoryDB(
        incident_id=incident.id,
        agent_id=agent.id,
        event_type="agent_dispatched",
        description=f"{decision_log} - Distance: {distance:.1f}km",
    ))

    logger.info("Agent {n} dispatched to incident {id} ({d:.1f}km)", n=agent.name, id=incident.id, d=distance)
    return agent


def seed_agents(db: Session) -> None:
    if db.query(AgentDB).count() > 0:
        return
    center_lat, center_lon = 40.7831, -73.9712
    agents_data = [
        ("Fire Engine 1", "fire", "🚒"),
        ("Fire Engine 2", "fire", "🚒"),
        ("Police Patrol 1", "police", "🚓"),
        ("Police Patrol 2", "police", "🚓"),
        ("Ambulance 1", "medical", "🚑"),
        ("Ambulance 2", "medical", "🚑"),
    ]
    for name, atype, icon in agents_data:
        if not db.query(AgentDB).filter(AgentDB.name == name).first():
            db.add(AgentDB(
                name=name,
                type=atype,
                icon=icon,
                status="available",
                lat=center_lat + random.uniform(-0.02, 0.02),
                lon=center_lon + random.uniform(-0.02, 0.02),
            ))
    db.commit()
    logger.info("Agents seeded")


def seed_stats(db: Session) -> None:
    if not db.query(StatsDB).first():
        db.add(StatsDB(total_incidents=0, active_incidents=0, resolved_incidents=0))
        db.commit()
        logger.info("Stats initialized")
