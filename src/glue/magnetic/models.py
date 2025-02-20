"""Pydantic models for GLUE magnetic field system"""

from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from pydantic import BaseModel, Field, field_validator

from ..core.types import AdhesiveType

# ==================== Flow Models ====================
class FlowConfig(BaseModel):
    """Configuration for a magnetic flow"""
    source: str = Field(..., description="Source team name")
    target: str = Field(..., description="Target team name")
    flow_type: str = Field(..., description="Flow type (push, pull, attract, repel)")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('flow_type')
    @classmethod
    def validate_flow_type(cls, v):
        if v not in {'push', 'pull', 'attract', 'repel'}:
            raise ValueError(f'Invalid flow type: {v}')
        return v

class FlowState(BaseModel):
    """Current state of a magnetic flow"""
    config: FlowConfig
    active: bool = Field(default=True)
    last_active: Optional[datetime] = Field(default=None)


# ==================== Event Models ====================
class FieldEvent(BaseModel):
    """Base model for field events"""
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FlowEstablishedEvent(FieldEvent):
    """Event for when a flow is established"""
    source_team: str = Field(..., description="Source team name")
    target_team: str = Field(..., description="Target team name")
    flow_type: str = Field(..., description="Flow type")

class FlowBrokenEvent(FieldEvent):
    """Event for when a flow is broken"""
    source_team: str = Field(..., description="Source team name")
    target_team: str = Field(..., description="Target team name")
    reason: Optional[str] = Field(default=None)

class TeamRepelledEvent(FieldEvent):
    """Event for when teams are set to repel"""
    team1: str = Field(..., description="First team name")
    team2: str = Field(..., description="Second team name")

class ResultsSharedEvent(FieldEvent):
    """Event for when results are shared"""
    source_team: str = Field(..., description="Source team name")
    target_team: str = Field(..., description="Target team name")
    result_type: str = Field(..., description="Type of result shared")

# ==================== Error Models ====================
class FlowError(BaseModel):
    """Model for flow errors"""
    flow_id: str = Field(..., description="Flow identifier")
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Dict[str, Any] = Field(default_factory=dict)

# ==================== Field Models ====================
class FieldConfig(BaseModel):
    """Configuration for a magnetic field"""
    name: str = Field(..., description="Field name")
    is_pull_team: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FieldState(BaseModel):
    """Current state of a magnetic field"""
    config: FieldConfig
    active: bool = Field(default=True)
    registered_teams: Set[str] = Field(default_factory=set)
    teams: Dict[str, Any] = Field(default_factory=dict)  # Maps team names to Team objects
    flows: Dict[str, FlowState] = Field(default_factory=dict)  # Maps flow IDs to flow states
    repelled_teams: Set[str] = Field(default_factory=set)

    class Config:
        arbitrary_types_allowed = True
