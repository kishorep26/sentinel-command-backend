from datetime import datetime
from typing import Optional
from pydantic import BaseModel


from pydantic import field_validator


class IncidentLoc(BaseModel):
    lat: float
    lon: float

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class IncidentIn(BaseModel):
    type: str
    location: IncidentLoc
    description: str
    status: Optional[str] = "active"


class IncidentOut(BaseModel):
    id: int
    type: str
    location: IncidentLoc
    description: str
    status: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class AgentOut(BaseModel):
    id: int
    name: str
    type: str
    icon: str
    status: str
    current_incident: Optional[str] = None
    decision: Optional[str] = None
    response_time: float
    efficiency: float
    total_responses: int
    successful_responses: int
    updated_at: Optional[datetime] = None
    lat: float
    lon: float
    fuel: float
    stress: float
    role: str
    status_message: Optional[str] = None

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    total_incidents: int
    active_incidents: int
    resolved_incidents: int
    average_response_time: float
    total_agents: int = 0
    active_agents: int = 0

    model_config = {"from_attributes": True}


class IncidentHistoryOut(BaseModel):
    id: int
    incident_id: Optional[int] = None
    agent_id: Optional[int] = None
    event_type: str
    description: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class StateUpdate(BaseModel):
    incidents: list[IncidentOut]
    agents: list[AgentOut]
    stats: StatsOut
    history: list[IncidentHistoryOut]
