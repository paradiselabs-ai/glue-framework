"""GLUE Magnetic Field System"""

from __future__ import annotations  # This enables forward references
from datetime import datetime
from typing import Dict, List, Optional, Type, Callable, Any, Set, Tuple, ClassVar, Annotated
from collections import defaultdict
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from prefect import task, flow
from loguru import logger

from ..core.debug import FieldDebugInfo, FlowDebugInfo
from ..core.pydantic_models import (
    ModelState, TeamContext, ToolResult, MagneticFlow, PrefectTaskConfig
)

from ..core.errors import (
    GlueError,
    FlowValidationError,
    FlowStateError,
    TeamRegistrationError,
    ProtectionMechanismError,
    PatternValidationError,
    handle_flow_errors,
    validate_flow_type,
    validate_team_registered
)
from ..core.logger import (
    log_flow_event,
    log_team_event,
    log_error,
    FlowLogContext,
    TeamLogContext
)
from ..core.debug import DebugEndpoints

# ==================== Models ====================
from .models import (
    FlowConfig,
    FlowState,
    FieldConfig,
    FieldState,
    FieldEvent,
    FlowEstablishedEvent,
    FlowBrokenEvent,
    TeamRepelledEvent,
    ResultsSharedEvent,
    FlowError
)

class _DebugInfo(BaseModel):
    """Debug information for magnetic field"""
    active_flows: Dict[str, bool] = Field(default_factory=dict, description="Currently active flows")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def get_flow_debug_info(self, flow_id: str) -> Dict[str, Any]:
        """Get debug information for a specific flow"""
        return {
            "active": self.active_flows.get(flow_id, False)
        }

# ==================== Main Class ====================
class MagneticField(BaseModel):
    """
    Manages team-to-team information flow using magnetic operators.
    
    Key Responsibilities:
    - Control how teams share information
    - Enforce team boundaries and relationships
    - Manage information flow between teams
    
    Magnetic Operators:
    - >< (Bidirectional): Teams can freely share information
    - -> (Push): Source team pushes results to target team
    - <- (Pull): Target team pulls results from source team
    - <> (Repel): Teams cannot communicate
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Configuration and state
    config: FieldConfig = Field(..., description="Field configuration")
    state: FieldState = Field(..., description="Field state")
    
    # Parent relationship
    parent: Optional[str] = Field(default=None, description="Parent field")
    workflow_id: Optional[str] = Field(default=None, description="Associated workflow ID")
    
    # Flow decorators
    establish_flow: ClassVar[Callable] = flow(name="establish_flow")
    break_flow: ClassVar[Callable] = flow(name="break_flow")
    transfer_information: ClassVar[Callable] = flow(name="transfer_information")
    
    # Task decorators
    add_team: ClassVar[Callable] = task()
    remove_team: ClassVar[Callable] = task()
    
    # Class-level field registry
    _fields: ClassVar[Dict[str, "MagneticField"]] = {}
    
    # Debug information
    debug: _DebugInfo = Field(default_factory=_DebugInfo)
    
    @classmethod
    def get_field(cls, name: str) -> Optional["MagneticField"]:
        """Get a magnetic field by name"""
        return cls._fields.get(name)
        
    name: str
    
    def __init__(
        self,
        name: str,
        is_pull_team: bool = False
    ) -> None:
        """Initialize a magnetic field with Pydantic models for validation"""
        # Set up logging
        logger.add(f"magnetic_field_{name}_{{time}}.log", rotation="10 MB")
        logger.info(f"Initializing MagneticField: {name}")
        
        # Initialize field configuration
        config = FieldConfig(
            name=name,
            is_pull_team=is_pull_team
        )
        
        # Initialize field state
        state = FieldState(
            config=config,
            active=True,
            registered_teams=set(),
            teams={},
            flows={},
            repelled_teams=set()
        )
        
        # Initialize base model
        super().__init__(
            name=name,
            config=config,
            state=state
        )
        
        # Initialize event handling
        self._event_handlers = defaultdict(list)
        self._debug_info = _DebugInfo()
        
        # Register this field
        MagneticField._fields[name] = self

    def _emit_event(self, event: FieldEvent) -> None:
        """
        Emit a field event to registered handlers.
        
        Args:
            event: The event to emit (FlowEstablishedEvent, FlowBrokenEvent, etc.)
        """
        event_type = type(event).__name__
        for handler in self._event_handlers[event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {str(e)}")

    def register_event_handler(self, event_type: str, handler: Callable[[FieldEvent], None]) -> None:
        """
        Register a handler for field events.
        
        Args:
            event_type: The type of event to handle (e.g. "FlowBrokenEvent")
            handler: The handler function to call when the event occurs
        """
        self._event_handlers[event_type].append(handler)

    # ==================== Debug Methods ====================
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information for this field"""
        return {
            "active_flows": len(self.state.flows),
            "registered_teams": len(self.state.registered_teams),
            "repelled_teams": len(self.state.repelled_teams)
        }
        
    def get_flow_debug_info(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """Get debug information for a specific flow"""
        if flow_id not in self.state.flows:
            return None
            
        flow = self.state.flows[flow_id]
        return {
            "source_team": flow.source_team,
            "target_team": flow.target_team,
            "flow_type": flow.flow_type,
            "active": True
        }

    def get_active_flows(self) -> Dict[str, MagneticFlow]:
        """
        Get all active flows in the field.
        
        Returns:
            Dict mapping flow IDs to their MagneticFlow objects
        """
        return self.state.flows.copy()

    def has_flow(self, source_team: str, target_team: str) -> bool:
        """
        Check if a flow exists between two teams.
        
        Args:
            source_team: The source team name
            target_team: The target team name
            
        Returns:
            True if a flow exists, False otherwise
        """
        flow_id = f"{source_team}->{target_team}"
        return flow_id in self.state.flows

    def get_flow_type(self, source_team: str, target_team: str) -> Optional[str]:
        """
        Get the type of flow between two teams.
        
        Args:
            source_team: The source team name
            target_team: The target team name
            
        Returns:
            The flow type if a flow exists, None otherwise
        """
        flow_id = f"{source_team}->{target_team}"
        flow = self.state.flows.get(flow_id)
        return flow.flow_type if flow else None
        
    # ==================== Core Methods ====================
    @handle_flow_errors
    @task(retries=3, retry_delay_seconds=10)
    async def add_team(self, team: Any) -> None:
        """Register a team with the magnetic field"""
        log_team_event(
            "Team Registration",
            TeamLogContext(
                team_name=team.name,
                action="register",
                metadata={"field": self.config.name}
            )
        )
        self.state.registered_teams.add(team.name)
        self.state.teams[team.name] = team
        
        log_flow_event(
            "Team Registration",
            FlowLogContext(
                flow_id=team.name,
                source_team=team.name,
                target_team=team.name,
                flow_type="registration",
                metadata={"field": self.config.name}
            )
        )

    @handle_flow_errors
    @flow(name="establish_flow")
    async def _establish_flow(
        self,
        source_team: str,
        target_team: str,
        flow_type: str,
        prefect_config: Optional[PrefectTaskConfig] = None
    ) -> None:
        """Internal method to establish a magnetic flow between teams"""
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
        source = self.state.teams[source_team]
        target = self.state.teams[target_team]

        if flow_type == "attract":
            source.relationships[target_team] = "attract"
            target.relationships[source_team] = "attract"
        elif flow_type == "push":
            source.relationships[target_team] = "push"
        elif flow_type == "pull":
            target.relationships[source_team] = "pull"
        elif flow_type == "repel":
            source.repelled_by.add(target_team)
            target.repelled_by.add(source_team)

        # Emit event
        self._emit_event(FlowEstablishedEvent(
            source_team=source_team,
            target_team=target_team,
            flow_type=flow_type
        ))

        self.state.updated_at = datetime.now()
        logger.info(f"Established {flow_type} flow from {source_team} to {target_team}")

    @handle_flow_errors
    @flow(name="break_flow")
    async def break_flow(
        self,
        source_team: str,
        target_team: str,
        reason: Optional[str] = None
    ) -> None:
        """
        Break a magnetic flow between teams.
        
        Args:
            source_team: The source team name
            target_team: The target team name
            reason: Optional reason for breaking the flow
        
        Raises:
            ValueError: If no flow exists between the teams
        """
        # Validate teams are registered
        validate_team_registered(source_team, self.state.registered_teams, "break_flow")
        validate_team_registered(target_team, self.state.registered_teams, "break_flow")
        
        flow_id = f"{source_team}->{target_team}"
        current_flow = self.state.flows.get(flow_id)
        
        if current_flow:
            # Remove flow
            del self.state.flows[flow_id]
            
            # Update team relationships
            source = self.state.teams[source_team]
            target = self.state.teams[target_team]

            if target_team in source.relationships:
                del source.relationships[target_team]
            if source_team in target.relationships:
                del target.relationships[source_team]
            
            # Emit event
            self._emit_event(FlowBrokenEvent(
                source_team=source_team,
                target_team=target_team,
                reason=reason
            ))
            
            log_flow_event(
                "Flow Broken Successfully",
                FlowLogContext(
                    flow_id=flow_id,
                    source_team=source_team,
                    target_team=target_team,
                    flow_type=current_flow.flow_type,
                    metadata={
                        "field": self.config.name
                    }
                )
            )
            
            self.state.updated_at = datetime.now()
            logger.info(f"Broke flow between {source_team} and {target_team}")
        else:
            log_error(
                "Flow Break Failed",
                f"No flow exists between {source_team} and {target_team}",
                "break_flow",
                {
                    "field": self.config.name,
                    "flow_id": flow_id
                }
            )
            raise ValueError(f"No flow exists between {source_team} and {target_team}")

    # Alias for break_flow to maintain backward compatibility
    break_team_flow = break_flow

    @handle_flow_errors
    @flow(name="cleanup_flows")
    async def cleanup_flows(self) -> None:
        """Clean up all team flows"""
        log_flow_event(
            "Starting Flow Cleanup",
            FlowLogContext(
                flow_id="cleanup",
                source_team="system",
                target_team="system",
                flow_type="cleanup",
                metadata={
                    "field": self.config.name,
                    "active_flows": len(self.state.flows),
                    "repelled_teams": len(self.state.repelled_teams)
                }
            )
        )
        
        # Clear all flows
        self.state.flows.clear()
        self.state.repelled_teams.clear()
        
        log_flow_event(
            "Flows Cleared",
            FlowLogContext(
                flow_id="cleanup",
                source_team="system",
                target_team="system",
                flow_type="cleanup",
                metadata={
                    "field": self.config.name,
                    "cleared_flows": len(self.state.flows)
                }
            )
        )

    def _validate_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if teams can interact using given magnetic operator.
        Returns (valid, internal_type) where valid is True if the flow is valid,
        and internal_type is the mapped flow type if valid is True.
        """
        flow_id = f"{source_team}_to_{target_team}"
        
        log_flow_event(
            "Starting Flow Validation",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type=operator,
                metadata={
                    "field": self.config.name,
                    "active_flows": len(self.state.flows),
                    "repelled_teams": len(self.state.repelled_teams)
                }
            )
        )
        
        # Validate teams exist
        if source_team not in self.state.teams:
            log_error(
                "Team Validation Failed",
                f"Source team {source_team} not found",
                "_validate_team_flow",
                {
                    "field": self.config.name,
                    "source_team": source_team
                }
            )
            return False, None
            
        if target_team not in self.state.teams:
            log_error(
                "Team Validation Failed",
                f"Target team {target_team} not found",
                "_validate_team_flow",
                {
                    "field": self.config.name,
                    "target_team": target_team
                }
            )
            return False, None

        # Check for repulsion
        source = self.state.teams[source_team]
        target = self.state.teams[target_team]

        if target_team in source.repelled_by or source_team in target.repelled_by:
            log_error(
                "Team Repulsion Check Failed",
                "Teams are repelled",
                "_validate_team_flow",
                {
                    "field": self.config.name,
                    "source_team": source_team,
                    "target_team": target_team
                }
            )
            return False, None

        # Map operator to internal type
        if operator == '><':
            internal_type = "attract"
        elif operator == '->':
            internal_type = "push"
        elif operator == '<-':
            internal_type = "pull"
        elif operator == '<>':
            internal_type = "repel"
        else:
            log_error(
                "Flow Validation Failed",
                f"Invalid operator: {operator}",
                "_validate_team_flow",
                {
                    "field": self.config.name,
                    "operator": operator
                }
            )
            return False, None

        # Check existing flows
        if internal_type == "attract":
            valid = not any(
                f"{source_team}:{target_team}" in self.state.repelled_teams 
                for flow_state in self.state.flows.values()
                if flow_state.source_team == source_team
            )
            if not valid:
                log_error(
                    "Bidirectional Flow Validation Failed",
                    "Existing repulsion prevents bidirectional flow",
                    "_validate_team_flow",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "operator": operator
                    }
                )
                return False, None
            
        elif internal_type == "push":
            valid = not any(
                f"{source_team}:{t}" in self.state.repelled_teams 
                for flow_state in self.state.flows.values()
                if flow_state.source_team == source_team
            )
            if not valid:
                log_error(
                    "Push Flow Validation Failed",
                    "Existing repulsion prevents push flow",
                    "_validate_team_flow",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "operator": operator
                    }
                )
                return False, None
            
        elif internal_type == "pull":
            valid = not any(
                f"{t}:{source_team}" in self.state.repelled_teams 
                for flow_state in self.state.flows.values()
                if flow_state.target_team == source_team
            )
            if not valid:
                log_error(
                    "Pull Flow Validation Failed",
                    "Existing repulsion prevents pull flow",
                    "_validate_team_flow",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "operator": operator
                    }
                )
                return False, None
            
        log_flow_event(
            "Flow Validation Successful",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type=operator,
                metadata={
                    "field": self.config.name,
                    "validation_result": "success"
                }
            )
        )
        return True, internal_type
        
    @handle_flow_errors
    @flow(name="set_team_flow")
    async def set_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str,  # "><", "->", "<-", or "<>"
        prefect_config: Optional[PrefectTaskConfig] = None
    ) -> None:
        """
        Set up magnetic flow between teams using GLUE expression operators.
        
        Args:
            source_team: The source team name
            target_team: The target team name
            operator: The magnetic operator to use ("><", "->", "<-", or "<>")
            prefect_config: Optional Prefect task configuration
            
        Raises:
            ValueError: If the flow is invalid
        """
        logger.info(f"Setting up {operator} flow from {source_team} to {target_team}")

        # Validate flow
        valid, internal_type = self._validate_team_flow(source_team, target_team, operator)
        if not valid:
            raise ValueError(f"Invalid flow {operator} between {source_team} and {target_team}")

        # Establish flow
        await self._establish_flow(source_team, target_team, internal_type, prefect_config)
