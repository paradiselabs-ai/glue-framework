"""GLUE Magnetic Field System"""

import logging
from typing import Dict, List, Optional, Type, Callable, Any, TYPE_CHECKING
from collections import defaultdict
from .rules import RuleSet

if TYPE_CHECKING:
    from ..core.context import ContextState

# ==================== Event Types ====================
class FieldEvent:
    """Base class for field events"""
    pass

class FlowEstablishedEvent(FieldEvent):
    """Event fired when a flow is established between teams"""
    def __init__(self, source_team: str, target_team: str, flow_type: str):
        self.source_team = source_team
        self.target_team = target_team
        self.flow_type = flow_type

class FlowBrokenEvent(FieldEvent):
    """Event fired when a flow is broken between teams"""
    def __init__(self, source_team: str, target_team: str):
        self.source_team = source_team
        self.target_team = target_team

class TeamRepelledEvent(FieldEvent):
    """Event fired when teams are set to repel each other"""
    def __init__(self, team1: str, team2: str):
        self.team1 = team1
        self.team2 = team2

class ResultsSharedEvent(FieldEvent):
    """Event fired when results are shared between teams"""
    def __init__(self, source_team: str, target_team: str, result_type: str):
        self.source_team = source_team
        self.target_team = target_team
        self.result_type = result_type

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
    def __init__(
        self,
        name: str,
        parent: Optional['MagneticField'] = None,
        is_pull_team: bool = False
    ):  
        self.name = name
        self.parent = parent
        self._active = False
        self._event_handlers = defaultdict(list)
        self._child_fields = []
        
        # Team configuration
        self.is_pull_team = is_pull_team  # Whether this team can pull from others
        
        # Initialize logger
        self.logger = logging.getLogger(f"glue.magnetic.field.{name}")

        # Team tracking
        self._registered_teams = set()  # Track registered teams

        # Configure team flows
        self._setup_flows()

    async def add_team(self, team: Any) -> None:
        """Register a team with the magnetic field"""
        self.logger.debug(f"Registering team: {team.name}")
        self._registered_teams.add(team.name)

    def _setup_flows(self):
        """Configure team-to-team flows"""
        self._flows = {}  # source_team -> {target_team -> flow_type}
        self._shared_results = {}  # team -> shared results
        self._repelled_teams = set()  # teams that cannot interact

    async def break_team_flow(
        self,
        source_team: str,
        target_team: str
    ) -> None:
        """Break an existing flow between teams"""
        if source_team in self._flows and target_team in self._flows[source_team]:
            del self._flows[source_team][target_team]
            if not self._flows[source_team]:  # Clean up empty dict
                del self._flows[source_team]
            
        # Clean up shared results
        if source_team in self._shared_results:
            del self._shared_results[source_team]

    async def cleanup_flows(self) -> None:
        """Clean up all team flows"""
        # Clear all flows
        self._flows.clear()
        self._shared_results.clear()
        self._repelled_teams.clear()
        
        # Clean up child fields
        for child in self._child_fields:
            await child.cleanup_flows()
        self._child_fields.clear()

    def _validate_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str
    ) -> bool:
        """Validate if teams can interact using given magnetic operator"""
        # Check if teams are registered
        if source_team not in self._registered_teams or target_team not in self._registered_teams:
            return False

        # Check repulsion first
        repelled_key = f"{source_team}:{target_team}"
        if repelled_key in self._repelled_teams:
            return False
            
        # Validate operator
        if operator not in ['><', '->', '<-', '<>']:
            return False
            
        # Check existing flows
        if operator == '><':
            return not any(f"{source_team}:{target_team}" in self._repelled_teams for target_team in self._flows.get(source_team, {}))
        elif operator == '->':
            return not any(f"{source_team}:{t}" in self._repelled_teams for t in self._flows.get(source_team, {}))
        elif operator == '<-':
            return not any(f"{t}:{source_team}" in self._repelled_teams for t in self._flows.get(target_team, {}))
            
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

    async def _setup_flow(
        self,
        source_team: str,
        target_team: str,
        flow_type: str  # "><", "->", "<-", "<>"
    ) -> None:
        """Set up flow between teams using magnetic operators"""
        # Initialize flow dictionaries if needed
        if source_team not in self._flows:
            self._flows[source_team] = {}
            
        # Set up flow based on operator
        if flow_type == "><":
            # Bidirectional flow
            self._flows[source_team][target_team] = flow_type
            if target_team not in self._flows:
                self._flows[target_team] = {}
            self._flows[target_team][source_team] = flow_type
            self._emit_event(FlowEstablishedEvent(source_team, target_team, "><"))
        elif flow_type == "->":
            # Push flow
            self._flows[source_team][target_team] = flow_type
            self._emit_event(FlowEstablishedEvent(source_team, target_team, "->"))
        elif flow_type == "<-":
            # Pull flow
            if target_team not in self._flows:
                self._flows[target_team] = {}
            self._flows[target_team][source_team] = "->"  # Target pulls from source
            self._emit_event(FlowEstablishedEvent(target_team, source_team, "<-"))
        elif flow_type == "<>":
            # Repulsion - remove any existing flows
            if target_team in self._flows[source_team]:
                del self._flows[source_team][target_team]
            if target_team in self._flows and source_team in self._flows[target_team]:
                del self._flows[target_team][source_team]
            # Add to repelled teams
            self._repelled_teams.add(f"{source_team}:{target_team}")
            self._repelled_teams.add(f"{target_team}:{source_team}")
            self._emit_event(TeamRepelledEvent(source_team, target_team))

    def create_child_field(self, name: str, is_pull_team: bool = False) -> 'MagneticField':
        """Create a child field that inherits from this field"""
        child = MagneticField(
            name=name,
            parent=self,
            is_pull_team=is_pull_team
        )
        self._child_fields.append(child)
        return child
        
    def get_child_field(self, name: str) -> Optional['MagneticField']:
        """Get a child field by name"""
        for child in self._child_fields:
            if child.name == name:
                return child
        return None
        
    def _is_repelled(self, other: 'MagneticField') -> bool:
        """Check if this field is repelled from another"""
        # Check if there's a repulsion in either direction
        if not self.parent or not other.parent:
            return False
            
        workflow = self.parent.workflow
        if not workflow:
            return False
            
        return (
            (self.name, other.name) in workflow.repulsions or
            (other.name, self.name) in workflow.repulsions
        )

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
        if source_team in self._flows and target_team in self._flows[source_team]:
            return self._flows[source_team][target_team]
        return None
        
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
        return self._flows.get(team_name, {}).copy()

    def __str__(self) -> str:
        """String representation of the magnetic field"""
        flows = []
        for source, targets in self._flows.items():
            for target, flow_type in targets.items():
                flows.append(f"{source} {flow_type} {target}")
        return f"MagneticField({self.name}, flows=[{', '.join(flows)}])"

    async def share_team_results(
        self,
        source_team: str,
        target_team: str,
        results: Dict[str, Any]
    ) -> None:
        """Share results between teams based on magnetic flow"""
        flow_type = self._get_flow_type(source_team, target_team)
        if not flow_type:
            raise ValueError(f"No magnetic flow defined between {source_team} and {target_team}")
            
        # Store results
        if source_team not in self._shared_results:
            self._shared_results[source_team] = {}
        self._shared_results[source_team][target_team] = results
        
        # Emit event
        for result_type in results.keys():
            self._emit_event(ResultsSharedEvent(source_team, target_team, result_type))

    async def enable_field_pull(self, source_field: 'MagneticField') -> bool:
        """Enable pulling from another field"""
        if not self.is_pull_team:
            return False
            
        try:
            await self.process_team_flow(self.name, source_field.name, None, "<-")
            return True
        except ValueError:
            return False
            
    async def enable_pull(self, target_team: str, source_team: str) -> bool:
        """Enable one-way pull flow from source team to target team"""
        try:
            await self.process_team_flow(target_team, source_team, None, "<-")
            return True
        except ValueError:
            return False

    async def enable_push(self, source_team: str, target_team: str) -> bool:
        """Enable one-way push flow from source team to target team"""
        try:
            await self.process_team_flow(source_team, target_team, None, "->")
            return True
        except ValueError:
            return False
