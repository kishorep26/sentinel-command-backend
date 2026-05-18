import json
from fastapi import WebSocket
from loguru import logger
from sqlalchemy.orm import Session

from app.models.models import AgentDB, IncidentDB, IncidentHistoryDB, StatsDB


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket client connected ({n} total)", n=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws) if hasattr(self._connections, "discard") else None
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("WebSocket client disconnected ({n} remaining)", n=len(self._connections))

    async def broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_state(self, db: Session) -> None:
        if not self._connections:
            return

        incidents = db.query(IncidentDB).all()
        agents = db.query(AgentDB).all()
        history = db.query(IncidentHistoryDB).order_by(IncidentHistoryDB.timestamp.desc()).limit(50).all()

        active_count = sum(1 for i in incidents if i.status != "resolved")
        total = len(incidents)
        resolved = total - active_count
        stats_row = db.query(StatsDB).first()
        avg_rt = stats_row.average_response_time if stats_row else 0.0

        payload = {
            "incidents": [
                {
                    "id": i.id,
                    "type": i.type,
                    "location": {"lat": i.lat, "lon": i.lon},
                    "description": i.description,
                    "status": i.status,
                    "timestamp": (i.created_at or i.timestamp).isoformat(),
                }
                for i in incidents
            ],
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.type,
                    "icon": a.icon or "",
                    "status": a.status,
                    "current_incident": a.current_incident,
                    "decision": a.decision,
                    "response_time": a.response_time,
                    "efficiency": a.efficiency,
                    "total_responses": a.total_responses,
                    "successful_responses": a.successful_responses,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                    "lat": a.lat,
                    "lon": a.lon,
                    "fuel": a.fuel,
                    "stress": a.stress,
                    "role": a.role,
                    "status_message": a.status_message,
                }
                for a in agents
            ],
            "stats": {
                "total_incidents": total,
                "active_incidents": active_count,
                "resolved_incidents": resolved,
                "average_response_time": avg_rt,
                "total_agents": len(agents),
                "active_agents": sum(1 for a in agents if a.status != "available"),
            },
            "history": [
                {
                    "id": h.id,
                    "incident_id": h.incident_id,
                    "agent_id": h.agent_id,
                    "event_type": h.event_type,
                    "description": h.description,
                    "timestamp": h.timestamp.isoformat(),
                }
                for h in history
            ],
        }

        await self.broadcast(payload)


ws_manager = ConnectionManager()
