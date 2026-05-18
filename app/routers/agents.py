from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.models import AgentDB, IncidentDB, IncidentHistoryDB
from app.schemas.schemas import AgentOut
from app.services.dispatch import INCIDENT_TYPE_MAP, haversine
from app.websocket.manager import ws_manager

router = APIRouter(tags=["agents"])


def _to_out(agent: AgentDB) -> AgentOut:
    return AgentOut(
        id=agent.id,
        name=agent.name,
        type=agent.type,
        icon=agent.icon or "",
        status=agent.status,
        current_incident=agent.current_incident,
        decision=agent.decision,
        response_time=agent.response_time,
        efficiency=agent.efficiency,
        total_responses=agent.total_responses,
        successful_responses=agent.successful_responses,
        updated_at=agent.updated_at,
        lat=agent.lat,
        lon=agent.lon,
        fuel=agent.fuel,
        stress=agent.stress,
        role=agent.role,
        status_message=agent.status_message,
    )


@router.get("/agents", response_model=list[AgentOut])
def get_agents(db: Session = Depends(get_session)):
    from app.main import run_request_tick
    run_request_tick()
    return [_to_out(a) for a in db.query(AgentDB).all()]


@router.post("/assign-agent")
def assign_agent(incident_id: int, db: Session = Depends(get_session)):
    incident = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not incident:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.assigned_agent_id:
        return {"message": "Agent already assigned", "agent_id": incident.assigned_agent_id}

    preferred_type = INCIDENT_TYPE_MAP.get(incident.type.lower(), "police")
    available = db.query(AgentDB).filter(
        AgentDB.status == "available",
        AgentDB.type == preferred_type,
    ).all() or db.query(AgentDB).filter(AgentDB.status == "available").all()

    if not available:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No available agents")

    nearest = min(available, key=lambda a: haversine(incident.lat, incident.lon, a.lat, a.lon))
    dist = haversine(incident.lat, incident.lon, nearest.lat, nearest.lon)

    incident.assigned_agent_id = nearest.id
    nearest.status = "busy"
    nearest.current_incident = str(incident.id)
    nearest.decision = f"Manual assignment to {incident.type}"
    nearest.response_time = dist * 2
    nearest.total_responses += 1
    nearest.updated_at = datetime.now()

    db.add(IncidentHistoryDB(
        incident_id=incident.id,
        agent_id=nearest.id,
        event_type="agent_assigned",
        description=f"Agent {nearest.name} manually assigned ({dist:.2f}km)",
    ))
    db.commit()
    return {"status": "assigned", "agent": _to_out(nearest)}


@router.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
