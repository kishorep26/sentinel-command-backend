from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class IncidentDB(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True)
    lat = Column(Float)
    lon = Column(Float)
    description = Column(String)
    status = Column(String, default="active")
    assigned_agent_id = Column(Integer, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    created_at = Column(DateTime, default=datetime.now)


class AgentDB(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String, index=True)
    icon = Column(String, nullable=True)
    status = Column(String, default="available")
    current_incident = Column(String, nullable=True)
    decision = Column(String, nullable=True)
    response_time = Column(Float, default=0.0)
    efficiency = Column(Float, default=90.0)
    fuel = Column(Float, default=100.0)
    stress = Column(Float, default=0.0)
    role = Column(String, default="standard")
    status_message = Column(String, nullable=True)
    total_responses = Column(Integer, default=0)
    successful_responses = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    lat = Column(Float, default=0.0)
    lon = Column(Float, default=0.0)


class StatsDB(Base):
    __tablename__ = "stats"

    id = Column(Integer, primary_key=True, index=True)
    total_incidents = Column(Integer, default=0)
    active_incidents = Column(Integer, default=0)
    resolved_incidents = Column(Integer, default=0)
    average_response_time = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class IncidentHistoryDB(Base):
    __tablename__ = "incident_history"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, index=True, nullable=True)
    agent_id = Column(Integer, index=True, nullable=True)
    event_type = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.now, index=True)


# ── Training Platform ──────────────────────────────────────────────────────────

class ScenarioDB(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    difficulty = Column(String, default="intermediate")   # beginner | intermediate | advanced
    duration_minutes = Column(Integer, default=10)
    # List of {at_seconds, type, lat, lon, description}
    events = Column(JSON, default=list)
    created_by = Column(String, nullable=True)            # Clerk user_id
    tenant_id = Column(String, nullable=True, index=True) # Clerk org_id or user_id
    is_template = Column(Boolean, default=False)          # seeded / pre-built
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class TrainingSessionDB(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, index=True)
    scenario_name = Column(String)
    trainee_id = Column(String, index=True)              # Clerk user_id
    trainee_name = Column(String, nullable=True)
    status = Column(String, default="active")            # active | completed | abandoned
    score = Column(Integer, default=0)
    max_score = Column(Integer, default=0)
    correct_dispatches = Column(Integer, default=0)
    total_dispatches = Column(Integer, default=0)
    avg_response_ms = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    # Detailed per-event breakdown stored as JSON
    event_results = Column(JSON, default=list)


def create_tables(engine) -> None:
    Base.metadata.create_all(bind=engine)
