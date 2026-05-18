from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from loguru import logger

from app.core.database import get_session
from app.core.clerk_auth import verify_clerk_token, require_instructor, get_user_id
from app.models.models import ScenarioDB, TrainingSessionDB

router = APIRouter(tags=["training"], prefix="/training")

# ── Pydantic schemas ────────────────────────────────────────────────────────────

class ScenarioEvent(BaseModel):
    at_seconds: int
    type: str
    lat: float
    lon: float
    description: str


class ScenarioCreate(BaseModel):
    name: str
    description: str
    difficulty: str = "intermediate"
    duration_minutes: int = 10
    events: list[ScenarioEvent]


class ScenarioOut(BaseModel):
    id: int
    name: str
    description: str
    difficulty: str
    duration_minutes: int
    events: list
    is_template: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class SessionStartIn(BaseModel):
    scenario_id: int
    trainee_name: Optional[str] = None


class EventResultIn(BaseModel):
    event_index: int
    incident_type: str         # what was actually dispatched
    expected_type: str         # what should have been dispatched
    response_time_ms: int


class SessionCompleteIn(BaseModel):
    event_results: list[EventResultIn]


class SessionOut(BaseModel):
    id: int
    scenario_id: int
    scenario_name: str
    trainee_id: str
    trainee_name: Optional[str]
    status: str
    score: int
    max_score: int
    correct_dispatches: int
    total_dispatches: int
    avg_response_ms: int
    started_at: datetime
    completed_at: Optional[datetime]
    event_results: list
    model_config = {"from_attributes": True}


# ── Scoring ────────────────────────────────────────────────────────────────────

_CORRECT_DISPATCH_PTS = 100
_SPEED_BONUS_THRESHOLD_MS = 8000   # under 8s = speed bonus
_SPEED_BONUS_PTS = 25
_WRONG_DISPATCH_PTS = -25

def _score_event(result: EventResultIn) -> int:
    points = 0
    if result.incident_type == result.expected_type:
        points += _CORRECT_DISPATCH_PTS
        if result.response_time_ms < _SPEED_BONUS_THRESHOLD_MS:
            points += _SPEED_BONUS_PTS
    else:
        points += _WRONG_DISPATCH_PTS
    return max(0, points)


# ── Seed pre-built scenarios ───────────────────────────────────────────────────

TEMPLATE_SCENARIOS = [
    {
        "name": "First Responder Basics",
        "description": "Single-agency incidents, one at a time. Learn the dispatch fundamentals.",
        "difficulty": "beginner",
        "duration_minutes": 5,
        "events": [
            {"at_seconds": 10, "type": "fire", "lat": 40.7614, "lon": -73.9776, "description": "Kitchen fire reported at residential building"},
            {"at_seconds": 60, "type": "medical", "lat": 40.7580, "lon": -73.9855, "description": "Elderly person collapsed on sidewalk"},
            {"at_seconds": 120, "type": "police", "lat": 40.7549, "lon": -73.9840, "description": "Shoplifting in progress at convenience store"},
            {"at_seconds": 190, "type": "fire", "lat": 40.7630, "lon": -73.9710, "description": "Vehicle fire on highway ramp"},
            {"at_seconds": 260, "type": "medical", "lat": 40.7560, "lon": -73.9890, "description": "Cyclist hit by car, conscious but injured"},
        ],
    },
    {
        "name": "Urban Crisis",
        "description": "Overlapping incidents across multiple agencies. Manage competing priorities.",
        "difficulty": "intermediate",
        "duration_minutes": 8,
        "events": [
            {"at_seconds": 5,  "type": "fire",    "lat": 40.7614, "lon": -73.9776, "description": "Gas leak explosion in apartment building"},
            {"at_seconds": 20, "type": "medical", "lat": 40.7615, "lon": -73.9774, "description": "Three occupants with burn injuries from explosion"},
            {"at_seconds": 45, "type": "police",  "lat": 40.7580, "lon": -73.9855, "description": "Armed robbery — suspect fled south on foot"},
            {"at_seconds": 90, "type": "accident","lat": 40.7549, "lon": -73.9840, "description": "Multi-vehicle collision blocking main road — injuries reported"},
            {"at_seconds": 140,"type": "medical", "lat": 40.7549, "lon": -73.9841, "description": "Driver trapped in vehicle, unconscious"},
            {"at_seconds": 200,"type": "fire",    "lat": 40.7630, "lon": -73.9710, "description": "Secondary fire spreading from initial explosion"},
            {"at_seconds": 280,"type": "police",  "lat": 40.7560, "lon": -73.9890, "description": "Crowd control required at explosion scene"},
        ],
    },
    {
        "name": "Mass Casualty Event",
        "description": "Coordinated multi-agency response under extreme pressure. All unit types required simultaneously.",
        "difficulty": "advanced",
        "duration_minutes": 10,
        "events": [
            {"at_seconds": 5,  "type": "fire",    "lat": 40.7614, "lon": -73.9776, "description": "Chemical factory fire — structural integrity compromised"},
            {"at_seconds": 15, "type": "medical", "lat": 40.7615, "lon": -73.9774, "description": "Multiple workers exposed to toxic gas — mass casualty"},
            {"at_seconds": 15, "type": "police",  "lat": 40.7613, "lon": -73.9778, "description": "Perimeter lockdown required — evacuate 3-block radius"},
            {"at_seconds": 60, "type": "fire",    "lat": 40.7630, "lon": -73.9710, "description": "Adjacent building ignited by chemical reaction"},
            {"at_seconds": 90, "type": "medical", "lat": 40.7580, "lon": -73.9855, "description": "Pedestrians affected by smoke — 8 casualties on street"},
            {"at_seconds": 120,"type": "police",  "lat": 40.7560, "lon": -73.9890, "description": "Looters reported at evacuation perimeter"},
            {"at_seconds": 180,"type": "fire",    "lat": 40.7549, "lon": -73.9840, "description": "Explosion risk — tertiary building has gas main rupture"},
            {"at_seconds": 240,"type": "medical", "lat": 40.7630, "lon": -73.9710, "description": "Firefighter casualty — requires immediate medical support"},
            {"at_seconds": 300,"type": "accident","lat": 40.7614, "lon": -73.9800, "description": "Emergency vehicle collision at scene perimeter"},
        ],
    },
]


def seed_scenarios(db: Session) -> None:
    existing = db.query(ScenarioDB).filter(ScenarioDB.is_template == True).count()
    if existing >= len(TEMPLATE_SCENARIOS):
        return
    for s in TEMPLATE_SCENARIOS:
        exists = db.query(ScenarioDB).filter(ScenarioDB.name == s["name"]).first()
        if not exists:
            db.add(ScenarioDB(
                name=s["name"],
                description=s["description"],
                difficulty=s["difficulty"],
                duration_minutes=s["duration_minutes"],
                events=s["events"],
                is_template=True,
            ))
    db.commit()
    logger.info("Training scenarios seeded")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_session)):
    return db.query(ScenarioDB).order_by(ScenarioDB.difficulty).all()


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: int, db: Session = Depends(get_session)):
    s = db.query(ScenarioDB).filter(ScenarioDB.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return s


@router.post("/scenarios", response_model=ScenarioOut, dependencies=[Depends(require_instructor)])
def create_scenario(
    body: ScenarioCreate,
    db: Session = Depends(get_session),
    claims: dict = Depends(verify_clerk_token),
):
    scenario = ScenarioDB(
        name=body.name,
        description=body.description,
        difficulty=body.difficulty,
        duration_minutes=body.duration_minutes,
        events=[e.model_dump() for e in body.events],
        created_by=claims.get("sub"),
        is_template=False,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.post("/sessions/start", response_model=SessionOut)
def start_session(
    body: SessionStartIn,
    db: Session = Depends(get_session),
    user_id: str = Depends(get_user_id),
):
    scenario = db.query(ScenarioDB).filter(ScenarioDB.id == body.scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    session = TrainingSessionDB(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        trainee_id=user_id,
        trainee_name=body.trainee_name,
        max_score=len(scenario.events) * (_CORRECT_DISPATCH_PTS + _SPEED_BONUS_PTS),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Training session {id} started by {user}", id=session.id, user=user_id)
    return session


@router.post("/sessions/{session_id}/complete", response_model=SessionOut)
def complete_session(
    session_id: int,
    body: SessionCompleteIn,
    db: Session = Depends(get_session),
    user_id: str = Depends(get_user_id),
):
    session = db.query(TrainingSessionDB).filter(
        TrainingSessionDB.id == session_id,
        TrainingSessionDB.trainee_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "completed":
        return session

    results = body.event_results
    total_score = sum(_score_event(r) for r in results)
    correct = sum(1 for r in results if r.incident_type == r.expected_type)
    avg_ms = int(sum(r.response_time_ms for r in results) / len(results)) if results else 0

    session.score = total_score
    session.correct_dispatches = correct
    session.total_dispatches = len(results)
    session.avg_response_ms = avg_ms
    session.status = "completed"
    session.completed_at = datetime.now()
    session.event_results = [r.model_dump() for r in results]

    db.commit()
    db.refresh(session)
    logger.info("Session {id} completed — score {score}/{max}", id=session_id, score=total_score, max=session.max_score)
    return session


@router.get("/sessions", response_model=list[SessionOut])
def my_sessions(
    db: Session = Depends(get_session),
    user_id: str = Depends(get_user_id),
):
    return db.query(TrainingSessionDB).filter(
        TrainingSessionDB.trainee_id == user_id,
    ).order_by(TrainingSessionDB.started_at.desc()).limit(20).all()


@router.get("/instructor/sessions", response_model=list[SessionOut], dependencies=[Depends(require_instructor)])
def all_sessions(db: Session = Depends(get_session)):
    return db.query(TrainingSessionDB).order_by(
        TrainingSessionDB.started_at.desc()
    ).limit(100).all()
