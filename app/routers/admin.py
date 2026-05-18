from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.security import verify_api_key
from app.models.models import AgentDB, IncidentDB, IncidentHistoryDB, StatsDB

router = APIRouter(tags=["admin"])


@router.get("/")
def root():
    return {"message": "Sentinel Command Backend API", "status": "online"}


@router.get("/health")
def health(db: Session = Depends(get_session)):
    from sqlalchemy import text
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/reset", dependencies=[Depends(verify_api_key)])
def reset_system(db: Session = Depends(get_session)):
    try:
        db.query(IncidentHistoryDB).delete()
        db.query(IncidentDB).delete()
        db.query(AgentDB).delete()
        db.query(StatsDB).delete()

        db.add(StatsDB(total_incidents=0, active_incidents=0, resolved_incidents=0))

        center_lat, center_lon = 40.7831, -73.9712
        seed_data = [
            ("Fire Engine 1", "fire", "🚒", 0.01, -0.01),
            ("Fire Engine 2", "fire", "🚒", -0.01, 0.01),
            ("Police Patrol 1", "police", "🚓", 0.02, 0.0),
            ("Police Patrol 2", "police", "🚓", -0.02, 0.0),
            ("Ambulance 1", "medical", "🚑", 0.0, 0.02),
            ("Ambulance 2", "medical", "🚑", 0.0, -0.02),
        ]
        for name, atype, icon, dlat, dlon in seed_data:
            db.add(AgentDB(
                name=name,
                type=atype,
                icon=icon,
                status="available",
                lat=center_lat + dlat,
                lon=center_lon + dlon,
                fuel=100.0,
                stress=0.0,
                role="standard",
                status_message="Patrolling Sector",
            ))

        db.commit()
        return {"status": "reset_complete", "message": "System reset to factory state"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
