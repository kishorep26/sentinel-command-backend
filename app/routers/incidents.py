from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_session
from app.core.security import verify_api_key
from app.models.models import IncidentDB, StatsDB
from app.schemas.schemas import IncidentIn, IncidentOut, IncidentLoc
from app.services import ai as ai_service
from app.services import dispatch as dispatch_service
from app.services.dispatch import INCIDENT_TYPE_MAP

router = APIRouter(tags=["incidents"])


def _to_out(incident: IncidentDB) -> IncidentOut:
    return IncidentOut(
        id=incident.id,
        type=incident.type,
        location=IncidentLoc(lat=incident.lat, lon=incident.lon),
        description=incident.description,
        status=incident.status,
        timestamp=incident.created_at or incident.timestamp,
    )


@router.get("/incidents", response_model=list[IncidentOut])
def get_incidents(db: Session = Depends(get_session)):
    return [_to_out(i) for i in db.query(IncidentDB).all()]


@router.post("/incidents", response_model=list[IncidentOut], dependencies=[Depends(verify_api_key)])
def create_incident(incident: IncidentIn, db: Session = Depends(get_session)):
    """
    Create one or more incidents from a situation report.
    Complex emergencies (e.g. fire + casualties + crime) produce multiple incidents,
    each with an appropriate unit dispatched automatically.
    """
    if incident.type in ("auto", "unknown", ""):
        classified = ai_service.ai_classify_multi(incident.description)
    else:
        # Manual type override — single incident
        mapped = INCIDENT_TYPE_MAP.get(incident.type.lower(), incident.type)
        classified = [{"type": mapped, "severity": 7, "description": incident.description}]

    created: list[IncidentOut] = []
    try:
        stats = db.query(StatsDB).first()
        for item in classified:
            new_incident = IncidentDB(
                type=item["type"],
                description=item["description"],
                status="active",
                lat=incident.location.lat,
                lon=incident.location.lon,
                timestamp=datetime.now(),
                created_at=datetime.now(),
            )
            db.add(new_incident)
            db.flush()

            dispatch_service.assign_agent(new_incident, db)

            if stats:
                stats.total_incidents += 1
                stats.active_incidents += 1

        db.commit()
        for item_db in db.query(IncidentDB).order_by(IncidentDB.id.desc()).limit(len(classified)).all():
            db.refresh(item_db)
        created = [_to_out(i) for i in db.query(IncidentDB).order_by(IncidentDB.id.desc()).limit(len(classified)).all()][::-1]
        logger.info("Created {n} incident(s) from single report", n=len(created))
        return created

    except Exception as exc:
        db.rollback()
        logger.exception("Error creating incident(s)")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/incidents/{incident_id}/resolve", response_model=IncidentOut, dependencies=[Depends(verify_api_key)])
def resolve_incident(incident_id: int, db: Session = Depends(get_session)):
    from app.models.models import AgentDB, IncidentHistoryDB

    incident = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status == "resolved":
        return _to_out(incident)

    incident.status = "resolved"

    if incident.assigned_agent_id:
        agent = db.query(AgentDB).filter(AgentDB.id == incident.assigned_agent_id).first()
        if agent:
            agent.status = "available"
            agent.current_incident = None
            agent.decision = "Mission Complete - Returning to Patrol"
            agent.successful_responses += 1
            agent.status_message = "Patrolling sector"
            agent.stress = max(0, agent.stress - 20)
            db.add(IncidentHistoryDB(
                incident_id=incident_id,
                agent_id=agent.id,
                event_type="mission_complete",
                description=f"Incident resolved by {agent.name}. Safety score increased.",
            ))

    stats = db.query(StatsDB).first()
    if stats:
        stats.active_incidents = max(0, stats.active_incidents - 1)
        stats.resolved_incidents += 1

    db.commit()
    db.refresh(incident)
    return _to_out(incident)
