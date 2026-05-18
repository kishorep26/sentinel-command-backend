import math
import random
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.models import IncidentDB, AgentDB, StatsDB, IncidentHistoryDB
from app.schemas.schemas import StatsOut, IncidentHistoryOut

router = APIRouter(tags=["analytics"])


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_session)):
    from app.main import run_request_tick
    run_request_tick()
    active = db.query(IncidentDB).filter(IncidentDB.status != "resolved").count()
    total = db.query(IncidentDB).count()
    resolved = db.query(IncidentDB).filter(IncidentDB.status == "resolved").count()
    total_agents = db.query(AgentDB).count()
    active_agents = db.query(AgentDB).filter(AgentDB.status != "available").count()
    stats = db.query(StatsDB).first()
    avg_rt = stats.average_response_time if stats else 0.0
    return StatsOut(
        total_incidents=total,
        active_incidents=active,
        resolved_incidents=resolved,
        average_response_time=avg_rt,
        total_agents=total_agents,
        active_agents=active_agents,
    )


@router.get("/incident-history", response_model=list[IncidentHistoryOut])
def get_incident_history(db: Session = Depends(get_session)):
    return db.query(IncidentHistoryDB).order_by(IncidentHistoryDB.timestamp.desc()).limit(50).all()


@router.get("/analytics/prediction")
def predict_risk_zones(db: Session = Depends(get_session)):
    incidents = db.query(IncidentDB).all()
    if len(incidents) < 5:
        return {"status": "insufficient_data", "message": "Need at least 5 incidents"}

    points = [(i.lat, i.lon) for i in incidents]
    k = min(5, len(points) // 5) + 1
    centers, clusters = _kmeans(points, k)

    zones = []
    for i, (center, cluster) in enumerate(zip(centers, clusters)):
        if not cluster:
            continue
        risk = len(cluster) / len(points)
        zones.append({
            "id": i,
            "lat": center[0],
            "lon": center[1],
            "risk_score": risk,
            "radius": 500 + risk * 2000,
            "label": "HIGH RISK ZONE" if risk > 0.3 else "MODERATE RISK ZONE",
        })

    zones.sort(key=lambda z: z["risk_score"], reverse=True)
    return {"status": "success", "zones": zones, "algorithm": "custom_kmeans_v1"}


def _kmeans(data: list[tuple], k: int, max_iter: int = 10):
    centroids = random.sample(data, k)
    for _ in range(max_iter):
        clusters: list[list] = [[] for _ in range(k)]
        for point in data:
            dists = [math.hypot(point[0] - c[0], point[1] - c[1]) for c in centroids]
            clusters[dists.index(min(dists))].append(point)
        new_centroids = []
        for i in range(k):
            if clusters[i]:
                new_centroids.append((
                    sum(p[0] for p in clusters[i]) / len(clusters[i]),
                    sum(p[1] for p in clusters[i]) / len(clusters[i]),
                ))
            else:
                new_centroids.append(centroids[i])
        if new_centroids == centroids:
            break
        centroids = new_centroids
    return centroids, clusters
