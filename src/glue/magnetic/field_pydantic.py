"""Magnetic field implementation with Pydantic and Prefect integration"""

from typing import Dict, Set, Any, Optional, List
from datetime import datetime
from prefect import task, flow
from pydantic import BaseModel, Field

from ..core.pydantic_models import (
    ModelState, TeamContext, ToolResult, PrefectTaskConfig,
    MagneticFlow
)

class FlowPattern(BaseModel):
    """Model for magnetic flow patterns"""
    name: str = Field(..., description="Pattern name")
    teams: List[str] = Field(..., description="Teams involved in pattern")
    flows: List[Dict[str, Any]] = Field(..., description="Flow configurations")
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PatternState(BaseModel):
    """Model for pattern execution state"""
    pattern: FlowPattern
    active_flows: Set[str] = Field(default_factory=set)
    message_counts: Dict[str, int] = Field(default_factory=dict)
    current_phase: Optional[str] = Field(default=None)

class FlowMetrics(BaseModel):
    """Model for flow performance metrics"""
    flow_id: str = Field(..., description="Flow identifier")
    message_count: int = Field(default=0)
    average_latency: float = Field(default=0.0)
    success_rate: float = Field(default=1.0)
    last_active: Optional[datetime] = Field(default=None)

class DebugInfo(BaseModel):
    """Debug information for magnetic field"""
    active_flows: Set[str] = Field(default_factory=set)
    flow_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    pattern_states: Dict[str, PatternState] = Field(default_factory=dict)
from ..core.types import AdhesiveType
from ..core.logger import get_logger
from ..core.team_pydantic import Team

logger = get_logger("magnetic")

class FieldState(BaseModel):
    """Current state of a magnetic field"""
    name: str
    teams: Dict[str, Team] = Field(default_factory=dict)
    flows: Dict[str, MagneticFlow] = Field(default_factory=dict)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

class MagneticField:
    """
    Magnetic field implementation with Prefect workflow orchestration.
    
    Features:
    - Team relationship management
    - Flow-based information transfer
    - Prefect task orchestration
    - State persistence
    - Error recovery
    """
    
    def __init__(self, name: str):
        self.state = FieldState(name=name)
        self.logger = logger
        self._active_patterns: Dict[str, PatternState] = {}
        self._debug_info = DebugInfo()
        self._metrics: Dict[str, FlowMetrics] = {}

    @flow(name="register_pattern")
    async def register_pattern(self, pattern: FlowPattern) -> None:
        """Register a new flow pattern"""
        if pattern.name in self._active_patterns:
            raise ValueError(f"Pattern {pattern.name} already exists")
            
        # Initialize pattern state
        self._active_patterns[pattern.name] = PatternState(
            pattern=pattern,
            active_flows=set(),
            message_counts={},
            current_phase=pattern.teams[0] if pattern.teams else None
        )
        
        self.logger.info(f"Registered pattern {pattern.name}")

    @flow(name="set_team_flow")
    async def set_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str,
        prefect_config: Optional[PrefectTaskConfig] = None
    ) -> None:
        """Set up magnetic flow between teams"""
        flow_id = f"{source_team}_to_{target_team}"
        
        # Create flow
        flow = MagneticFlow(
            source_team=source_team,
            target_team=target_team,
            flow_type=operator,
            prefect_config=prefect_config
        )
        
        # Store flow
        self.state.flows[flow_id] = flow
        self._debug_info.active_flows.add(flow_id)
        
        # Initialize metrics
        self._metrics[flow_id] = FlowMetrics(
            flow_id=flow_id,
            message_count=0,
            average_latency=0.0,
            success_rate=1.0
        )
        
        self.logger.info(f"Set up {operator} flow from {source_team} to {target_team}")

    @flow(name="advance_pattern_phase")
    async def advance_pattern_phase(self, pattern_name: str) -> bool:
        """Advance a pattern to its next phase"""
        if pattern_name not in self._active_patterns:
            raise ValueError(f"Pattern {pattern_name} not found")
            
        pattern_state = self._active_patterns[pattern_name]
        pattern = pattern_state.pattern
        
        if not pattern_state.current_phase:
            return False
            
        # Find next phase
        current_idx = pattern.teams.index(pattern_state.current_phase)
        next_idx = (current_idx + 1) % len(pattern.teams)
        next_phase = pattern.teams[next_idx]
        
        # Update pattern state
        pattern_state.current_phase = next_phase
        self.logger.info(f"Advanced pattern {pattern_name} to phase {next_phase}")
        return True

    def get_pattern_state(self, pattern_name: str) -> Optional[PatternState]:
        """Get the current state of a pattern"""
        return self._active_patterns.get(pattern_name)

    def get_debug_info(self) -> DebugInfo:
        """Get debug information about the field"""
        return self._debug_info

    def get_flow_metrics(self, flow_id: str) -> Dict[str, float]:
        """Get metrics for a specific flow"""
        if flow_id not in self._metrics:
            return {}
            
        metrics = self._metrics[flow_id]
        return {
            "message_rate": metrics.message_count / max((datetime.now() - metrics.last_active).total_seconds(), 1) if metrics.last_active else 0,
            "error_rate": 1 - metrics.success_rate,
            "latency": metrics.average_latency,
            "throughput": metrics.message_count,
            "uptime": (datetime.now() - metrics.last_active).total_seconds() if metrics.last_active else 0
        }

class DebugInfo(BaseModel):
    """Debug information for magnetic field"""
    active_flows: Set[str] = Field(default_factory=set)
    flow_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    pattern_states: Dict[str, PatternState] = Field(default_factory=dict)

    @task
    async def add_team(self, team: Team) -> None:
        """Add a team to the field"""
        if team.name in self.state.teams:
            raise ValueError(f"Team {team.name} already exists in field {self.state.name}")
            
        self.state.teams[team.name] = team
        self.state.updated_at = datetime.now()
        self.logger.info(f"Added team {team.name} to field {self.state.name}")

    @task
    async def remove_team(self, team_name: str) -> None:
        """Remove a team from the field"""
        if team_name not in self.state.teams:
            raise ValueError(f"Team {team_name} not found in field {self.state.name}")
            
        # Remove all flows involving this team
        flows_to_remove = []
        for flow_id, flow in self.state.flows.items():
            if flow.source_team == team_name or flow.target_team == team_name:
                flows_to_remove.append(flow_id)
                
        for flow_id in flows_to_remove:
            del self.state.flows[flow_id]
            
        del self.state.teams[team_name]
        self.state.updated_at = datetime.now()
        self.logger.info(f"Removed team {team_name} from field {self.state.name}")

    @flow(name="establish_flow")
    async def establish_flow(
        self,
        source_team: str,
        target_team: str,
        flow_type: str,
        prefect_config: Optional[PrefectTaskConfig] = None
    ) -> None:
        """Establish a magnetic flow between teams"""
        # Validate teams
        if source_team not in self.state.teams:
            raise ValueError(f"Source team {source_team} not found")
        if target_team not in self.state.teams:
            raise ValueError(f"Target team {target_team} not found")
            
        # Check for repulsion
        source = self.state.teams[source_team]
        target = self.state.teams[target_team]
        
        if target_team in source.repelled_by or source_team in target.repelled_by:
            raise ValueError(f"Cannot establish flow - teams are repelled")
            
        # Create flow
        flow = MagneticFlow(
            source_team=source_team,
            target_team=target_team,
            flow_type=flow_type,
            prefect_config=prefect_config
        )
        
        # Store flow
        flow_id = f"{source_team}->{target_team}"
        self.state.flows[flow_id] = flow
        
        # Update team relationships
        if flow_type == "push":
            source.relationships[target_team] = AdhesiveType.GLUE
        elif flow_type == "pull":
            target.relationships[source_team] = AdhesiveType.GLUE
        elif flow_type == "repel":
            source.repelled_by.add(target_team)
            target.repelled_by.add(source_team)
            
        self.state.updated_at = datetime.now()
        self.logger.info(f"Established {flow_type} flow from {source_team} to {target_team}")

    @flow(name="break_flow")
    async def break_flow(self, source_team: str, target_team: str) -> None:
        """Break a magnetic flow between teams"""
        flow_id = f"{source_team}->{target_team}"
        if flow_id not in self.state.flows:
            raise ValueError(f"No flow exists between {source_team} and {target_team}")
            
        # Remove flow
        flow = self.state.flows.pop(flow_id)
        
        # Update team relationships
        source = self.state.teams[source_team]
        target = self.state.teams[target_team]
        
        if target_team in source.relationships:
            del source.relationships[target_team]
        if source_team in target.relationships:
            del target.relationships[source_team]
            
        self.state.updated_at = datetime.now()
        self.logger.info(f"Broke flow between {source_team} and {target_team}")

    @flow(name="transfer_information")
    async def transfer_information(
        self,
        source_team: str,
        target_team: str,
        content: Any,
        adhesive_type: Optional[AdhesiveType] = None
    ) -> None:
        """Transfer information between teams based on flow"""
        flow_id = f"{source_team}->{target_team}"
        if flow_id not in self.state.flows:
            raise ValueError(f"No flow exists between {source_team} and {target_team}")
            
        flow = self.state.flows[flow_id]
        source = self.state.teams[source_team]
        target = self.state.teams[target_team]
        
        # Use flow's adhesive type if none specified
        if adhesive_type is None:
            adhesive_type = source.relationships.get(target_team, AdhesiveType.TAPE)
            
        # Transfer based on flow type
        if flow.flow_type == "push":
            await target.receive_results({
                "transfer": ToolResult(
                    tool_name="magnetic_transfer",
                    result=content,
                    adhesive=adhesive_type,
                    timestamp=datetime.now()
                )
            })
        elif flow.flow_type == "pull":
            await source.share_results_with(target)
            
        self.state.updated_at = datetime.now()
        self.logger.info(f"Transferred information from {source_team} to {target_team}")

    def get_team_flows(self, team_name: str) -> Dict[str, str]:
        """Get all flows involving a team"""
        flows = {}
        for flow_id, flow in self.state.flows.items():
            if flow.source_team == team_name:
                flows[flow.target_team] = "->"
            elif flow.target_team == team_name:
                flows[flow.source_team] = "<-"
        return flows

    def get_repelled_teams(self, team_name: str) -> Set[str]:
        """Get all teams that repel the given team"""
        if team_name not in self.state.teams:
            raise ValueError(f"Team {team_name} not found")
        return self.state.teams[team_name].repelled_by

    def is_flow_active(self, source_team: str, target_team: str) -> bool:
        """Check if a flow exists and is active between teams"""
        flow_id = f"{source_team}->{target_team}"
        return flow_id in self.state.flows
