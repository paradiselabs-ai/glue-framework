"""GLUE Magnetic Field System"""

from datetime import datetime
from typing import Dict, List, Optional, Type, Callable, Any, TYPE_CHECKING
from collections import defaultdict

from ..core.errors import (
    GlueError,
    FlowValidationError,
    FlowStateError,
    TeamRegistrationError,
    ProtectionMechanismError,
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
from .rules import RuleSet

if TYPE_CHECKING:
    from ..core.context import ContextState

# ==================== Event Types ====================
from .models import (
    FlowConfig,
    FlowState,
    FlowMetrics,
    FieldConfig,
    FieldState,
    FieldEvent,
    FlowEstablishedEvent,
    FlowBrokenEvent,
    TeamRepelledEvent,
    ResultsSharedEvent,
    FlowError,
    RecoveryAction,
    CircuitBreaker,
    RateLimiter,
    RetryStrategy,
    FlowHealth
)

# ==================== Main Class ====================
class MagneticField:
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
    
    Example:
        ```glue
        magnetize {
            research {
                lead = researcher
                tools = [web_search]
            }
            
            docs {
                lead = writer
                tools = [file_handler]
            }
            
            flow {
                research -> docs  # Research pushes to docs
                docs <- pull     # Docs can pull from research
            }
        }
        ```
    """
    
    _fields: Dict[str, 'MagneticField'] = {}
    
    @classmethod
    def get_field(cls, name: str) -> Optional['MagneticField']:
        """Get a magnetic field by name"""
        return cls._fields.get(name)
        
    def __init__(
        self,
        name: str,
        parent: Optional['MagneticField'] = None,
        is_pull_team: bool = False
    ):  
        # Initialize field configuration
        self.config = FieldConfig(
            name=name,
            is_pull_team=is_pull_team,
            parent_field=parent.config.name if parent else None
        )
        
        # Initialize field state
        self.state = FieldState(config=self.config)
        
        # Set up parent relationship
        self.parent = parent
        
        # Initialize event handling
        self._event_handlers = defaultdict(list)
        
        # Initialize logger
        self.logger = logging.getLogger(f"glue.magnetic.field.{name}")
        
        # Register this field
        MagneticField._fields[name] = self
        
        # Initialize protection mechanisms
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._retry_strategies: Dict[str, RetryStrategy] = {}
        self._health_monitors: Dict[str, FlowHealth] = {}

    # ==================== Debug Methods ====================
    def get_debug_info(self) -> FieldDebugInfo:
        """Get debug information for this field"""
        return DebugEndpoints.get_field_debug_info(self)
        
    def get_flow_debug_info(self, flow_id: str) -> Optional[FlowDebugInfo]:
        """Get debug information for a specific flow"""
        return DebugEndpoints.get_flow_debug_info(self, flow_id)
        
    def get_flow_metrics(self, flow_id: str) -> Dict[str, Any]:
        """Get detailed metrics for a flow"""
        return DebugEndpoints.get_flow_metrics(self, flow_id)
        
    def get_protection_status(self, flow_id: str) -> Dict[str, Any]:
        """Get detailed status of protection mechanisms for a flow"""
        return DebugEndpoints.get_protection_status(self, flow_id)

    # ==================== Core Methods ====================
    @handle_flow_errors
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
        
        # Initialize flow metrics for team
        flow_id = f"{team.name}_metrics"
        self._health_monitors[flow_id] = FlowHealth(
            flow_id=flow_id,
            latency=0.0,
            error_rate=0.0,
            throughput=1.0
        )
        log_flow_event(
            "Flow Metrics Initialized",
            FlowLogContext(
                flow_id=flow_id,
                source_team=team.name,
                target_team=team.name,
                flow_type="metrics",
                metadata={"field": self.config.name}
            )
        )
        
        # Initialize protection mechanisms for team
        self._circuit_breakers[flow_id] = CircuitBreaker(flow_id=flow_id)
        self._rate_limiters[flow_id] = RateLimiter(
            flow_id=flow_id,
            max_requests=100,
            window_seconds=60
        )
        self._retry_strategies[flow_id] = RetryStrategy()

    @handle_flow_errors
    async def break_team_flow(
        self,
        source_team: str,
        target_team: str,
        reason: Optional[str] = None
    ) -> None:
        """Break an existing flow between teams"""
        # Validate teams are registered
        validate_team_registered(source_team, self.state.registered_teams, "break_team_flow")
        validate_team_registered(target_team, self.state.registered_teams, "break_team_flow")
        
        flow_id = f"{source_team}_to_{target_team}"
        current_flow = self.state.active_flows.get(flow_id)
        
        log_flow_event(
            "Breaking Team Flow",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type=current_flow.config.flow_type if current_flow else "unknown",
                metadata={
                    "field": self.config.name,
                    "reason": reason,
                    "active_flows": len(self.state.active_flows)
                }
            )
        )
        
        if flow_id in self.state.active_flows:
            # Get current flow state
            flow_state = self.state.active_flows[flow_id]
            
            # Update health metrics
            if flow_id in self._health_monitors:
                health = self._health_monitors[flow_id]
                health.last_check = datetime.now()
            
            # Remove flow
            del self.state.active_flows[flow_id]
            
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
                    flow_type=flow_state.config.flow_type,
                    metadata={
                        "field": self.config.name,
                        "message_count": flow_state.message_count,
                        "active_flows": len(self.state.active_flows)
                    }
                )
            )
        else:
            log_error(
                "Flow Break Failed",
                f"No active flow between {source_team} and {target_team}",
                "break_team_flow",
                {
                    "field": self.config.name,
                    "flow_id": flow_id,
                    "active_flows": len(self.state.active_flows)
                }
            )

    @handle_flow_errors
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
                    "active_flows": len(self.state.active_flows),
                    "repelled_teams": len(self.state.repelled_teams),
                    "child_fields": len(self.state.child_fields)
                }
            )
        )
        
        # Clear all flows and states
        active_flow_count = len(self.state.active_flows)
        self.state.active_flows.clear()
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
                    "cleared_flows": active_flow_count
                }
            )
        )
        
        # Reset protection mechanisms
        self._circuit_breakers.clear()
        self._rate_limiters.clear()
        self._retry_strategies.clear()
        self._health_monitors.clear()
        
        # Clean up child fields
        if self.state.child_fields:
            child_count = len(self.state.child_fields)
            for child_name in self.state.child_fields:
                child = MagneticField.get_field(child_name)
                if child:
                    log_flow_event(
                        "Cleaning Child Field",
                        FlowLogContext(
                            flow_id=f"cleanup_{child_name}",
                            source_team="system",
                            target_team=child_name,
                            flow_type="cleanup",
                            metadata={
                                "parent_field": self.config.name,
                                "child_field": child_name
                            }
                        )
                    )
                    await child.cleanup_flows()
            
            self.state.child_fields.clear()
            
            log_flow_event(
                "Child Fields Cleaned",
                FlowLogContext(
                    flow_id="cleanup",
                    source_team="system",
                    target_team="system",
                    flow_type="cleanup",
                    metadata={
                        "field": self.config.name,
                        "cleaned_children": child_count
                    }
                )
            )

    def _validate_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str
    ) -> bool:
        """Validate if teams can interact using given magnetic operator"""
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
                    "active_flows": len(self.state.active_flows),
                    "repelled_teams": len(self.state.repelled_teams)
                }
            )
        )
        
        # Check if teams are registered
        if not (source_team in self.state.registered_teams and 
                target_team in self.state.registered_teams):
            log_error(
                "Team Registration Validation Failed",
                "One or both teams not registered",
                "_validate_team_flow",
                {
                    "field": self.config.name,
                    "source_registered": source_team in self.state.registered_teams,
                    "target_registered": target_team in self.state.registered_teams
                }
            )
            return False

        # Check repulsion
        repelled_key = f"{source_team}:{target_team}"
        if repelled_key in self.state.repelled_teams:
            log_error(
                "Team Repulsion Check Failed",
                "Teams are repelled",
                "_validate_team_flow",
                {
                    "field": self.config.name,
                    "repelled_key": repelled_key
                }
            )
            return False
            
        # Check circuit breaker
        if flow_id in self._circuit_breakers:
            breaker = self._circuit_breakers[flow_id]
            if not breaker.can_execute():
                log_error(
                    "Circuit Breaker Check Failed",
                    "Circuit breaker is open",
                    "_validate_team_flow",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "error_count": breaker.error_count,
                        "last_error": str(breaker.last_error)
                    }
                )
                return False
                
        # Check rate limiter
        if flow_id in self._rate_limiters:
            limiter = self._rate_limiters[flow_id]
            if not limiter.can_process():
                log_error(
                    "Rate Limit Check Failed",
                    "Rate limit exceeded",
                    "_validate_team_flow",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "current_rate": limiter.current_rate,
                        "max_rate": limiter.max_requests
                    }
                )
                return False
            
        # Validate operator
        validate_flow_type(operator, "_validate_team_flow")
            
        # Check existing flows
        if operator == '><':
            valid = not any(
                f"{source_team}:{target_team}" in self.state.repelled_teams 
                for flow_state in self.state.active_flows.values()
                if flow_state.config.source == source_team
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
            return valid
            
        elif operator == '->':
            valid = not any(
                f"{source_team}:{t}" in self.state.repelled_teams 
                for flow_state in self.state.active_flows.values()
                if flow_state.config.source == source_team
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
            return valid
            
        elif operator == '<-':
            valid = not any(
                f"{t}:{source_team}" in self.state.repelled_teams 
                for flow_state in self.state.active_flows.values()
                if flow_state.config.target == source_team
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
            return valid
            
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
        return True
        
    async def set_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str  # "><", "->", "<-", or "<>"
    ) -> None:
        """Set up magnetic flow between teams"""
        if not self._validate_team_flow(source_team, target_team, operator):
            raise ValueError(f"Invalid flow {operator} between {source_team} and {target_team}")
            
        # Set up flow based on operator
        await self._setup_flow(source_team, target_team, operator)

    @handle_flow_errors
    async def _setup_flow(
        self,
        source_team: str,
        target_team: str,
        flow_type: str  # "><", "->", "<-", "<>"
    ) -> None:
        """Set up flow between teams using magnetic operators"""
        flow_id = f"{source_team}_to_{target_team}"
        
        log_flow_event(
            "Starting Flow Setup",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type=flow_type,
                metadata={
                    "field": self.config.name,
                    "active_flows": len(self.state.active_flows)
                }
            )
        )
        
        # Validate teams are registered
        validate_team_registered(source_team, self.state.registered_teams, "_setup_flow")
        validate_team_registered(target_team, self.state.registered_teams, "_setup_flow")
        
        # Validate flow type
        validate_flow_type(flow_type, "_setup_flow")
        
        # Create flow configuration
        flow_config = FlowConfig(
            source=source_team,
            target=target_team,
            flow_type=flow_type,
            enabled=True,
            strength=1.0  # Default strength for new flows
        )
        
        # Create flow state
        flow_state = FlowState(
            config=flow_config,
            active=True,
            message_count=0,
            last_active=datetime.now(),
            error_count=0,
            last_error=None
        )
        
        log_flow_event(
            "Flow State Created",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type=flow_type,
                metadata={
                    "field": self.config.name,
                    "config": flow_config.dict(),
                    "state": flow_state.dict()
                }
            )
        )
        
        # Set up flow based on operator
        if flow_type == "><":
            forward_id = f"{source_team}_to_{target_team}"
            reverse_id = f"{target_team}_to_{source_team}"
            
            # Create bidirectional states
            self.state.active_flows[forward_id] = flow_state
            reverse_state = FlowState(
                config=FlowConfig(
                    source=target_team,
                    target=source_team,
                    flow_type=flow_type,
                    enabled=True,
                    strength=1.0
                ),
                active=True,
                message_count=0,
                last_active=datetime.now(),
                error_count=0,
                last_error=None
            )
            self.state.active_flows[reverse_id] = reverse_state
            
            log_flow_event(
                "Bidirectional Flow Established",
                FlowLogContext(
                    flow_id=forward_id,
                    source_team=source_team,
                    target_team=target_team,
                    flow_type="><",
                    metadata={
                        "field": self.config.name,
                        "forward_id": forward_id,
                        "reverse_id": reverse_id
                    }
                )
            )
            
            self._emit_event(FlowEstablishedEvent(
                source_team=source_team,
                target_team=target_team,
                flow_type="><",
                strength=1.0
            ))
            
        elif flow_type == "->":
            flow_id = f"{source_team}_to_{target_team}"
            self.state.active_flows[flow_id] = flow_state
            
            log_flow_event(
                "Push Flow Established",
                FlowLogContext(
                    flow_id=flow_id,
                    source_team=source_team,
                    target_team=target_team,
                    flow_type="->",
                    metadata={
                        "field": self.config.name,
                        "direction": "push"
                    }
                )
            )
            
            self._emit_event(FlowEstablishedEvent(
                source_team=source_team,
                target_team=target_team,
                flow_type="->",
                strength=1.0
            ))
            
        elif flow_type == "<-":
            # Pull flow - target pulls from source
            flow_id = f"{target_team}_to_{source_team}"
            pull_state = FlowState(
                config=FlowConfig(
                    source=target_team,
                    target=source_team,
                    flow_type="->",  # Convert to push from target's perspective
                    enabled=True,
                    strength=1.0
                ),
                active=True,
                message_count=0,
                last_active=datetime.now(),
                error_count=0,
                last_error=None
            )
            self.state.active_flows[flow_id] = pull_state
            
            log_flow_event(
                "Pull Flow Established",
                FlowLogContext(
                    flow_id=flow_id,
                    source_team=target_team,
                    target_team=source_team,
                    flow_type="<-",
                    metadata={
                        "field": self.config.name,
                        "direction": "pull",
                        "converted_type": "->"
                    }
                )
            )
            
            self._emit_event(FlowEstablishedEvent(
                source_team=target_team,
                target_team=source_team,
                flow_type="<-",
                strength=1.0
            ))
            
        elif flow_type == "<>":
            forward_id = f"{source_team}_to_{target_team}"
            reverse_id = f"{target_team}_to_{source_team}"
            
            # Remove any existing flows
            if forward_id in self.state.active_flows:
                del self.state.active_flows[forward_id]
            if reverse_id in self.state.active_flows:
                del self.state.active_flows[reverse_id]
                
            # Add to repelled teams
            repelled_key = f"{source_team}:{target_team}"
            reverse_key = f"{target_team}:{source_team}"
            self.state.repelled_teams.add(repelled_key)
            self.state.repelled_teams.add(reverse_key)
            
            log_flow_event(
                "Repulsion Established",
                FlowLogContext(
                    flow_id=f"repel_{source_team}_{target_team}",
                    source_team=source_team,
                    target_team=target_team,
                    flow_type="<>",
                    metadata={
                        "field": self.config.name,
                        "repelled_keys": [repelled_key, reverse_key],
                        "removed_flows": [forward_id, reverse_id]
                    }
                )
            )
            
            self._emit_event(TeamRepelledEvent(
                team1=source_team,
                team2=target_team
            ))
            
        # Initialize or update protection mechanisms
        if flow_type != "<>":  # Don't set up protection for repelled flows
            if flow_id not in self._circuit_breakers:
                self._circuit_breakers[flow_id] = CircuitBreaker(flow_id=flow_id)
            if flow_id not in self._rate_limiters:
                self._rate_limiters[flow_id] = RateLimiter(
                    flow_id=flow_id,
                    max_requests=100,
                    window_seconds=60
                )
            if flow_id not in self._retry_strategies:
                self._retry_strategies[flow_id] = RetryStrategy()
            if flow_id not in self._health_monitors:
                self._health_monitors[flow_id] = FlowHealth(
                    flow_id=flow_id,
                    latency=0.0,
                    error_rate=0.0,
                    throughput=1.0
                )
                
            log_flow_event(
                "Protection Mechanisms Initialized",
                FlowLogContext(
                    flow_id=flow_id,
                    source_team=source_team,
                    target_team=target_team,
                    flow_type=flow_type,
                    metadata={
                        "field": self.config.name,
                        "circuit_breaker": "initialized",
                        "rate_limiter": "initialized",
                        "retry_strategy": "initialized",
                        "health_monitor": "initialized"
                    }
                )
            )

    @handle_flow_errors
    def create_child_field(self, name: str, is_pull_team: bool = False) -> 'MagneticField':
        """Create a child field that inherits from this field"""
        log_flow_event(
            "Creating Child Field",
            FlowLogContext(
                flow_id=f"create_child_{name}",
                source_team="system",
                target_team=name,
                flow_type="create",
                metadata={
                    "field": self.config.name,
                    "child_name": name,
                    "is_pull_team": is_pull_team,
                    "current_children": len(self.state.child_fields)
                }
            )
        )
        
        # Check if child field already exists
        if name in self.state.child_fields:
            log_error(
                "Child Field Creation Failed",
                f"Child field {name} already exists",
                "create_child_field",
                {
                    "field": self.config.name,
                    "child_name": name,
                    "existing_children": list(self.state.child_fields)
                }
            )
            raise ValueError(f"Child field {name} already exists")
            
        # Create new child field
        child = MagneticField(
            name=name,
            parent=self,
            is_pull_team=is_pull_team
        )
        self.state.child_fields.add(child.config.name)
        
        log_flow_event(
            "Child Field Created Successfully",
            FlowLogContext(
                flow_id=f"create_child_{name}",
                source_team="system",
                target_team=name,
                flow_type="create",
                metadata={
                    "field": self.config.name,
                    "child_name": name,
                    "is_pull_team": is_pull_team,
                    "total_children": len(self.state.child_fields)
                }
            )
        )
        return child
        
    def get_child_field(self, name: str) -> Optional['MagneticField']:
        """Get a child field by name"""
        log_flow_event(
            "Retrieving Child Field",
            FlowLogContext(
                flow_id=f"get_child_{name}",
                source_team="system",
                target_team=name,
                flow_type="get",
                metadata={
                    "field": self.config.name,
                    "child_name": name,
                    "has_child": name in self.state.child_fields
                }
            )
        )
        
        if name in self.state.child_fields:
            child = MagneticField.get_field(name)
            if child:
                return child
                
        log_error(
            "Child Field Retrieval Failed",
            f"Child field {name} not found",
            "get_child_field",
            {
                "field": self.config.name,
                "child_name": name,
                "existing_children": list(self.state.child_fields)
            }
        )
        return None
        
    @handle_flow_errors
    def _is_repelled(self, other: 'MagneticField') -> bool:
        """Check if this field is repelled from another"""
        log_flow_event(
            "Checking Field Repulsion",
            FlowLogContext(
                flow_id=f"repel_check_{self.name}_{other.name}",
                source_team=self.name,
                target_team=other.name,
                flow_type="check",
                metadata={
                    "field": self.config.name,
                    "other_field": other.config.name,
                    "has_parent": bool(self.parent),
                    "other_has_parent": bool(other.parent)
                }
            )
        )
        
        # Check if either field lacks a parent
        if not self.parent or not other.parent:
            log_flow_event(
                "Repulsion Check Failed",
                FlowLogContext(
                    flow_id=f"repel_check_{self.name}_{other.name}",
                    source_team=self.name,
                    target_team=other.name,
                    flow_type="check",
                    metadata={
                        "field": self.config.name,
                        "reason": "Missing parent field",
                        "has_parent": bool(self.parent),
                        "other_has_parent": bool(other.parent)
                    }
                )
            )
            return False
            
        workflow = self.parent.workflow
        if not workflow:
            log_flow_event(
                "Repulsion Check Failed",
                FlowLogContext(
                    flow_id=f"repel_check_{self.name}_{other.name}",
                    source_team=self.name,
                    target_team=other.name,
                    flow_type="check",
                    metadata={
                        "field": self.config.name,
                        "reason": "No workflow defined"
                    }
                )
            )
            return False
            
        # Check for repulsion in either direction
        is_repelled = (
            (self.name, other.name) in workflow.repulsions or
            (other.name, self.name) in workflow.repulsions
        )
        
        log_flow_event(
            "Repulsion Check Complete",
            FlowLogContext(
                flow_id=f"repel_check_{self.name}_{other.name}",
                source_team=self.name,
                target_team=other.name,
                flow_type="check",
                metadata={
                    "field": self.config.name,
                    "is_repelled": is_repelled,
                    "workflow_name": workflow.name if workflow else None
                }
            )
        )
        return is_repelled

    def on_event(
        self,
        event_type: Type[FieldEvent],
        handler: Callable[[FieldEvent], None]
    ) -> None:
        """Register an event handler"""
        self._event_handlers[event_type].append(handler)

    def _emit_event(self, event: FieldEvent) -> None:
        """Emit an event to all registered handlers"""
        for handler in self._event_handlers[type(event)]:
            handler(event)
        # Propagate to parent field
        if self.parent:
            self.parent._emit_event(event)

    def _get_flow_type(self, source_team: str, target_team: str) -> Optional[str]:
        """Get the type of flow between teams"""
        flow_id = f"{source_team}_to_{target_team}"
        flow_state = self.state.active_flows.get(flow_id)
        if flow_state and flow_state.active:
            return flow_state.config.flow_type
        return None
        
    @handle_flow_errors
    async def attract(self, team1: str, team2: str) -> bool:
        """Attract two teams (bidirectional flow)"""
        flow_id = f"{team1}_to_{team2}"
        
        log_flow_event(
            "Starting Team Attraction",
            FlowLogContext(
                flow_id=flow_id,
                source_team=team1,
                target_team=team2,
                flow_type="><",
                metadata={
                    "field": self.config.name,
                    "operation": "attract"
                }
            )
        )
        
        try:
            # Validate teams are registered
            validate_team_registered(team1, self.state.registered_teams, "attract")
            validate_team_registered(team2, self.state.registered_teams, "attract")
            
            success = await self.process_team_flow(team1, team2, None, "><")
            if success:
                log_flow_event(
                    "Team Attraction Successful",
                    FlowLogContext(
                        flow_id=flow_id,
                        source_team=team1,
                        target_team=team2,
                        flow_type="><",
                        metadata={
                            "field": self.config.name,
                            "status": "success"
                        }
                    )
                )
                return True
            else:
                log_error(
                    "Team Attraction Failed",
                    "Failed to establish bidirectional flow",
                    "attract",
                    {
                        "field": self.config.name,
                        "team1": team1,
                        "team2": team2
                    }
                )
                return False
        except Exception as e:
            log_error(
                "Team Attraction Error",
                str(e),
                "attract",
                {
                    "field": self.config.name,
                    "team1": team1,
                    "team2": team2,
                    "error": str(e)
                }
            )
            return False
            
    @handle_flow_errors
    async def repel(self, team1: str, team2: str) -> bool:
        """Repel two teams (no communication)"""
        flow_id = f"repel_{team1}_{team2}"
        
        log_flow_event(
            "Starting Team Repulsion",
            FlowLogContext(
                flow_id=flow_id,
                source_team=team1,
                target_team=team2,
                flow_type="<>",
                metadata={
                    "field": self.config.name,
                    "operation": "repel"
                }
            )
        )
        
        try:
            # Validate teams are registered
            validate_team_registered(team1, self.state.registered_teams, "repel")
            validate_team_registered(team2, self.state.registered_teams, "repel")
            
            success = await self.process_team_flow(team1, team2, None, "<>")
            if success:
                log_flow_event(
                    "Team Repulsion Successful",
                    FlowLogContext(
                        flow_id=flow_id,
                        source_team=team1,
                        target_team=team2,
                        flow_type="<>",
                        metadata={
                            "field": self.config.name,
                            "status": "success",
                            "repelled_key": f"{team1}:{team2}"
                        }
                    )
                )
                return True
            else:
                log_error(
                    "Team Repulsion Failed",
                    "Failed to establish repulsion",
                    "repel",
                    {
                        "field": self.config.name,
                        "team1": team1,
                        "team2": team2
                    }
                )
                return False
        except Exception as e:
            log_error(
                "Team Repulsion Error",
                str(e),
                "repel",
                {
                    "field": self.config.name,
                    "team1": team1,
                    "team2": team2,
                    "error": str(e)
                }
            )
            return False
            
    async def process_team_flow(
        self,
        source_team: str,
        target_team: str,
        content: Any,
        flow_type: str  # "><", "->", "<-", "<>"
    ) -> Optional[Any]:
        """Process information flow between teams using magnetic operators"""
        if not self._validate_team_flow(source_team, target_team, flow_type):
            raise ValueError(f"Invalid flow {flow_type} between {source_team} and {target_team}")
            
        # Set up flow and emit event
        await self._setup_flow(source_team, target_team, flow_type)
        
        # Return content for all flows except repulsion
        return None if flow_type == "<>" else content
        
    def get_team_flows(self, team_name: str) -> Dict[str, str]:
        """Get all flows for a team"""
        flows = {}
        for flow_id, flow_state in self.state.active_flows.items():
            if flow_state.config.source == team_name:
                flows[flow_state.config.target] = flow_state.config.flow_type
        return flows

    def __str__(self) -> str:
        """String representation of the magnetic field"""
        flows = []
        for flow_id, flow_state in self.state.active_flows.items():
            if flow_state.active:
                source = flow_state.config.source
                target = flow_state.config.target
                flow_type = flow_state.config.flow_type
                flows.append(f"{source} {flow_type} {target}")
        
        repelled = [f"{t1}<>{t2}" for t1, t2 in [r.split(":") for r in self.state.repelled_teams]]
        
        return (
            f"MagneticField({self.config.name}, "
            f"flows=[{', '.join(flows)}], "
            f"repelled=[{', '.join(repelled)}])"
        )

    @handle_flow_errors
    async def share_team_results(
        self,
        source_team: str,
        target_team: str,
        results: Dict[str, Any]
    ) -> None:
        """Share results between teams based on magnetic flow"""
        flow_id = f"{source_team}_to_{target_team}"
        
        log_flow_event(
            "Starting Results Share",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type="share",
                metadata={
                    "field": self.config.name,
                    "result_types": list(results.keys()),
                    "total_size": sum(len(str(r)) for r in results.values())
                }
            )
        )
        
        # Validate teams are registered
        validate_team_registered(source_team, self.state.registered_teams, "share_team_results")
        validate_team_registered(target_team, self.state.registered_teams, "share_team_results")
        
        # Get flow state
        flow_state = self.state.active_flows.get(flow_id)
        if not flow_state or not flow_state.active:
            log_error(
                "Share Results Failed",
                f"No active flow between {source_team} and {target_team}",
                "share_team_results",
                {
                    "field": self.config.name,
                    "flow_id": flow_id,
                    "active_flows": len(self.state.active_flows)
                }
            )
            raise FlowStateError(f"No active flow between {source_team} and {target_team}")
        
        # Check protection mechanisms
        if flow_id in self._circuit_breakers:
            breaker = self._circuit_breakers[flow_id]
            if not breaker.can_execute():
                log_error(
                    "Circuit Breaker Blocked Share",
                    "Circuit breaker is open",
                    "share_team_results",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "error_count": breaker.error_count,
                        "last_error": str(breaker.last_error)
                    }
                )
                raise ProtectionMechanismError("Circuit breaker is open")
        
        if flow_id in self._rate_limiters:
            limiter = self._rate_limiters[flow_id]
            if not limiter.can_process():
                log_error(
                    "Rate Limit Blocked Share",
                    "Rate limit exceeded",
                    "share_team_results",
                    {
                        "field": self.config.name,
                        "flow_id": flow_id,
                        "current_rate": limiter.current_rate,
                        "max_rate": limiter.max_requests
                    }
                )
                raise ProtectionMechanismError("Rate limit exceeded")
            limiter.record_request()
        
        # Update flow state
        flow_state.message_count += 1
        flow_state.last_active = datetime.now()
        
        # Update health metrics
        if flow_id in self._health_monitors:
            health = self._health_monitors[flow_id]
            health.last_check = datetime.now()
            health.throughput = flow_state.message_count / max(
                (datetime.now() - flow_state.last_active).total_seconds(), 1
            )
        
        # Emit events for each result
        for result_type, result in results.items():
            result_size = len(str(result))
            log_flow_event(
                f"Sharing Result: {result_type}",
                FlowLogContext(
                    flow_id=flow_id,
                    source_team=source_team,
                    target_team=target_team,
                    flow_type="share",
                    metadata={
                        "field": self.config.name,
                        "result_type": result_type,
                        "size": result_size
                    }
                )
            )
            
            self._emit_event(ResultsSharedEvent(
                source_team=source_team,
                target_team=target_team,
                result_type=result_type,
                size=result_size
            ))
        
        log_flow_event(
            "Results Share Complete",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type="share",
                metadata={
                    "field": self.config.name,
                    "message_count": flow_state.message_count,
                    "throughput": health.throughput if flow_id in self._health_monitors else 0.0,
                    "shared_types": list(results.keys())
                }
            )
        )

    @handle_flow_errors
    async def enable_field_pull(self, source_field: 'MagneticField') -> bool:
        """Enable pulling from another field"""
        flow_id = f"{self.name}_from_{source_field.name}"
        
        log_flow_event(
            "Starting Field Pull Setup",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_field.name,
                target_team=self.name,
                flow_type="<-",
                metadata={
                    "field": self.config.name,
                    "is_pull_team": self.config.is_pull_team
                }
            )
        )
        
        if not self.config.is_pull_team:
            log_error(
                "Field Pull Setup Failed",
                "Field is not configured as a pull team",
                "enable_field_pull",
                {
                    "field": self.config.name,
                    "source_field": source_field.name
                }
            )
            return False
            
        try:
            success = await self.process_team_flow(self.name, source_field.name, None, "<-")
            if success:
                log_flow_event(
                    "Field Pull Enabled Successfully",
                    FlowLogContext(
                        flow_id=flow_id,
                        source_team=source_field.name,
                        target_team=self.name,
                        flow_type="<-",
                        metadata={
                            "field": self.config.name,
                            "status": "success"
                        }
                    )
                )
                return True
            else:
                log_error(
                    "Field Pull Setup Failed",
                    "Failed to establish pull flow",
                    "enable_field_pull",
                    {
                        "field": self.config.name,
                        "source_field": source_field.name
                    }
                )
                return False
        except Exception as e:
            log_error(
                "Field Pull Error",
                str(e),
                "enable_field_pull",
                {
                    "field": self.config.name,
                    "source_field": source_field.name,
                    "error": str(e)
                }
            )
            return False
            
    @handle_flow_errors
    async def enable_pull(self, target_team: str, source_team: str) -> bool:
        """Enable one-way pull flow from source team to target team"""
        flow_id = f"{target_team}_from_{source_team}"
        
        log_flow_event(
            "Starting Pull Flow Setup",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type="<-",
                metadata={
                    "field": self.config.name,
                    "operation": "enable_pull"
                }
            )
        )
        
        try:
            # Validate teams are registered
            validate_team_registered(target_team, self.state.registered_teams, "enable_pull")
            validate_team_registered(source_team, self.state.registered_teams, "enable_pull")
            
            success = await self.process_team_flow(target_team, source_team, None, "<-")
            if success:
                log_flow_event(
                    "Pull Flow Enabled Successfully",
                    FlowLogContext(
                        flow_id=flow_id,
                        source_team=source_team,
                        target_team=target_team,
                        flow_type="<-",
                        metadata={
                            "field": self.config.name,
                            "status": "success"
                        }
                    )
                )
                return True
            else:
                log_error(
                    "Pull Flow Setup Failed",
                    "Failed to establish pull flow",
                    "enable_pull",
                    {
                        "field": self.config.name,
                        "source_team": source_team,
                        "target_team": target_team
                    }
                )
                return False
        except Exception as e:
            log_error(
                "Pull Flow Error",
                str(e),
                "enable_pull",
                {
                    "field": self.config.name,
                    "source_team": source_team,
                    "target_team": target_team,
                    "error": str(e)
                }
            )
            return False

    @handle_flow_errors
    async def enable_push(self, source_team: str, target_team: str) -> bool:
        """Enable one-way push flow from source team to target team"""
        flow_id = f"{source_team}_to_{target_team}"
        
        log_flow_event(
            "Starting Push Flow Setup",
            FlowLogContext(
                flow_id=flow_id,
                source_team=source_team,
                target_team=target_team,
                flow_type="->",
                metadata={
                    "field": self.config.name,
                    "operation": "enable_push"
                }
            )
        )
        
        try:
            # Validate teams are registered
            validate_team_registered(source_team, self.state.registered_teams, "enable_push")
            validate_team_registered(target_team, self.state.registered_teams, "enable_push")
            
            success = await self.process_team_flow(source_team, target_team, None, "->")
            if success:
                log_flow_event(
                    "Push Flow Enabled Successfully",
                    FlowLogContext(
                        flow_id=flow_id,
                        source_team=source_team,
                        target_team=target_team,
                        flow_type="->",
                        metadata={
                            "field": self.config.name,
                            "status": "success"
                        }
                    )
                )
                return True
            else:
                log_error(
                    "Push Flow Setup Failed",
                    "Failed to establish push flow",
                    "enable_push",
                    {
                        "field": self.config.name,
                        "source_team": source_team,
                        "target_team": target_team
                    }
                )
                return False
        except Exception as e:
            log_error(
                "Push Flow Error",
                str(e),
                "enable_push",
                {
                    "field": self.config.name,
                    "source_team": source_team,
                    "target_team": target_team,
                    "error": str(e)
                }
            )
            return False
