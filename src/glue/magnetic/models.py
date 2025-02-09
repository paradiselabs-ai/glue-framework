"""Pydantic models for GLUE magnetic field system"""

from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from pydantic import BaseModel, Field, validator

from ..core.types import AdhesiveType

# ==================== Flow Models ====================
class FlowConfig(BaseModel):
    """Configuration for a magnetic flow"""
    source: str = Field(..., description="Source team name")
    target: str = Field(..., description="Target team name")
    flow_type: str = Field(..., description="Flow type (><, ->, <-, <>)")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Flow strength")
    enabled: bool = Field(default=True, description="Whether flow is enabled")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('flow_type')
    def validate_flow_type(cls, v):
        if v not in {'><', '->', '<-', '<>'}:
            raise ValueError(f'Invalid flow type: {v}')
        return v

class FlowState(BaseModel):
    """Current state of a magnetic flow"""
    config: FlowConfig
    active: bool = Field(default=True)
    message_count: int = Field(default=0)
    last_active: Optional[datetime] = Field(default=None)
    error_count: int = Field(default=0)
    last_error: Optional[datetime] = Field(default=None)

class FlowMetrics(BaseModel):
    """Performance metrics for a flow"""
    flow_id: str = Field(..., description="Flow identifier")
    message_count: int = Field(default=0)
    error_count: int = Field(default=0)
    average_latency: float = Field(default=0.0)
    success_rate: float = Field(default=1.0)
    last_active: Optional[datetime] = Field(default=None)
    last_error: Optional[datetime] = Field(default=None)

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
    strength: float = Field(default=1.0)

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
    size: Optional[int] = Field(default=None)

# ==================== Error Models ====================
class FlowError(BaseModel):
    """Model for flow errors"""
    flow_id: str = Field(..., description="Flow identifier")
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = Field(default=True)

class RecoveryAction(BaseModel):
    """Model for flow recovery actions"""
    error: FlowError
    action_type: str = Field(..., description="Type of recovery action")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)

# ==================== Field Models ====================
class FieldConfig(BaseModel):
    """Configuration for a magnetic field"""
    name: str = Field(..., description="Field name")
    is_pull_team: bool = Field(default=False)
    parent_field: Optional[str] = Field(default=None)
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FieldState(BaseModel):
    """Current state of a magnetic field"""
    config: FieldConfig
    active: bool = Field(default=True)
    registered_teams: Set[str] = Field(default_factory=set)
    active_flows: Dict[str, FlowState] = Field(default_factory=dict)
    repelled_teams: Set[str] = Field(default_factory=set)
    child_fields: List[str] = Field(default_factory=list)

# ==================== Protection Models ====================
class CircuitBreaker(BaseModel):
    """Circuit breaker for flow protection"""
    flow_id: str = Field(..., description="Flow identifier")
    error_threshold: int = Field(default=5)
    reset_timeout: int = Field(default=60)  # seconds
    error_count: int = Field(default=0)
    last_error: Optional[datetime] = Field(default=None)
    state: str = Field(default="closed")  # closed, open, half-open
    
    @validator('state')
    def validate_state(cls, v):
        if v not in {'closed', 'open', 'half-open'}:
            raise ValueError(f'Invalid circuit breaker state: {v}')
        return v

class RateLimiter(BaseModel):
    """Rate limiter for flow protection"""
    flow_id: str = Field(..., description="Flow identifier")
    max_requests: int = Field(..., description="Maximum requests per window")
    window_seconds: int = Field(..., description="Time window in seconds")
    current_count: int = Field(default=0)
    window_start: datetime = Field(default_factory=datetime.now)

class RetryStrategy(BaseModel):
    """Retry strategy for flow recovery"""
    initial_delay: float = Field(default=1.0)
    max_delay: float = Field(default=60.0)
    multiplier: float = Field(default=2.0)
    jitter: float = Field(default=0.1)

class FlowHealth(BaseModel):
    """Health monitoring for flows"""
    flow_id: str = Field(..., description="Flow identifier")
    latency: float = Field(default=0.0)
    error_rate: float = Field(default=0.0)
    throughput: float = Field(default=1.0)
    last_check: datetime = Field(default_factory=datetime.now)
