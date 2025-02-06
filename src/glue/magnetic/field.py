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
        self.logger.info(f"\n{'='*20} Breaking Team Flow {'='*20}")
        self.logger.info(f"Source Team: {source_team}")
        self.logger.info(f"Target Team: {target_team}")
        
        # Log current state
        self.logger.info("\nCurrent Flow State:")
        self.logger.info(f"Active Flows: {dict(self._flows)}")
        self.logger.info(f"Shared Results: {dict(self._shared_results)}")
        
        try:
            # Break flow
            if source_team in self._flows and target_team in self._flows[source_team]:
                flow_type = self._flows[source_team][target_team]
                self.logger.info(f"Breaking {flow_type} flow")
                del self._flows[source_team][target_team]
                if not self._flows[source_team]:  # Clean up empty dict
                    del self._flows[source_team]
                self.logger.info("Flow broken successfully")
            else:
                self.logger.info("No active flow to break")
            
            # Clean up shared results
            if source_team in self._shared_results:
                self.logger.info("Cleaning up shared results")
                del self._shared_results[source_team]
                self.logger.info("Shared results cleaned")
            
            # Log final state
            self.logger.info("\nFinal Flow State:")
            self.logger.info(f"Active Flows: {dict(self._flows)}")
            self.logger.info(f"{'='*50}\n")
            
        except Exception as e:
            self.logger.error(f"Error breaking flow: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            raise

    async def cleanup_flows(self) -> None:
        """Clean up all team flows"""
        self.logger.info(f"\n{'='*20} Cleaning Up Flows {'='*20}")
        
        # Log current state
        self.logger.info("\nCurrent State:")
        self.logger.info(f"Active Flows: {dict(self._flows)}")
        self.logger.info(f"Shared Results: {dict(self._shared_results)}")
        self.logger.info(f"Repelled Teams: {self._repelled_teams}")
        self.logger.info(f"Child Fields: {len(self._child_fields)}")
        
        try:
            # Clear all flows
            self.logger.info("\nClearing flows...")
            self._flows.clear()
            self.logger.info("Flows cleared")
            
            # Clear shared results
            self.logger.info("Clearing shared results...")
            self._shared_results.clear()
            self.logger.info("Shared results cleared")
            
            # Clear repelled teams
            self.logger.info("Clearing repelled teams...")
            self._repelled_teams.clear()
            self.logger.info("Repelled teams cleared")
            
            # Clean up child fields
            if self._child_fields:
                self.logger.info(f"\nCleaning up {len(self._child_fields)} child fields...")
                for child in self._child_fields:
                    self.logger.info(f"Cleaning up child field: {child.name}")
                    await child.cleanup_flows()
                self._child_fields.clear()
                self.logger.info("Child fields cleaned")
            
            self.logger.info("\nCleanup complete")
            self.logger.info(f"{'='*50}\n")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            raise

    def _validate_team_flow(
        self,
        source_team: str,
        target_team: str,
        operator: str
    ) -> bool:
        """Validate if teams can interact using given magnetic operator"""
        self.logger.info(f"\n{'='*20} Magnetic Field Validation {'='*20}")
        self.logger.info(f"Source Team: {source_team}")
        self.logger.info(f"Target Team: {target_team}")
        self.logger.info(f"Operator: {operator}")
        
        # Check if teams are registered
        if source_team not in self._registered_teams or target_team not in self._registered_teams:
            self.logger.error("Teams not registered")
            return False

        # Check repulsion first
        repelled_key = f"{source_team}:{target_team}"
        if repelled_key in self._repelled_teams:
            self.logger.error("Teams are repelled")
            return False
            
        # Validate operator
        if operator not in ['><', '->', '<-', '<>']:
            self.logger.error(f"Invalid operator: {operator}")
            return False
            
        # Check existing flows
        if operator == '><':
            valid = not any(f"{source_team}:{target_team}" in self._repelled_teams for target_team in self._flows.get(source_team, {}))
            self.logger.info("Bidirectional flow validation:")
            self.logger.info(f"- Existing flows: {self._flows.get(source_team, {})}")
            self.logger.info(f"- Valid: {valid}")
            return valid
        elif operator == '->':
            valid = not any(f"{source_team}:{t}" in self._repelled_teams for t in self._flows.get(source_team, {}))
            self.logger.info("Push flow validation:")
            self.logger.info(f"- Existing flows: {self._flows.get(source_team, {})}")
            self.logger.info(f"- Valid: {valid}")
            return valid
        elif operator == '<-':
            valid = not any(f"{t}:{source_team}" in self._repelled_teams for t in self._flows.get(target_team, {}))
            self.logger.info("Pull flow validation:")
            self.logger.info(f"- Existing flows: {self._flows.get(target_team, {})}")
            self.logger.info(f"- Valid: {valid}")
            return valid
            
        self.logger.info("Flow validation successful")
        self.logger.info(f"{'='*50}\n")
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
        self.logger.info(f"\n{'='*20} Magnetic Flow Setup {'='*20}")
        self.logger.info(f"Setting up {flow_type} flow:")
        self.logger.info(f"Source Team: {source_team}")
        self.logger.info(f"Target Team: {target_team}")
        
        # Initialize flow dictionaries if needed
        if source_team not in self._flows:
            self._flows[source_team] = {}
            self.logger.info(f"Initialized flow dictionary for {source_team}")
            
        # Set up flow based on operator
        if flow_type == "><":
            self.logger.info("Setting up bidirectional flow")
            # Bidirectional flow
            self._flows[source_team][target_team] = flow_type
            if target_team not in self._flows:
                self._flows[target_team] = {}
            self._flows[target_team][source_team] = flow_type
            self._emit_event(FlowEstablishedEvent(source_team, target_team, "><"))
            self.logger.info("Bidirectional flow established")
            
        elif flow_type == "->":
            self.logger.info("Setting up push flow")
            # Push flow
            self._flows[source_team][target_team] = flow_type
            self._emit_event(FlowEstablishedEvent(source_team, target_team, "->"))
            self.logger.info("Push flow established")
            
        elif flow_type == "<-":
            self.logger.info("Setting up pull flow")
            # Pull flow
            if target_team not in self._flows:
                self._flows[target_team] = {}
            self._flows[target_team][source_team] = "->"  # Target pulls from source
            self._emit_event(FlowEstablishedEvent(target_team, source_team, "<-"))
            self.logger.info("Pull flow established")
            
        elif flow_type == "<>":
            self.logger.info("Setting up repulsion")
            # Repulsion - remove any existing flows
            if target_team in self._flows[source_team]:
                del self._flows[source_team][target_team]
            if target_team in self._flows and source_team in self._flows[target_team]:
                del self._flows[target_team][source_team]
            # Add to repelled teams
            self._repelled_teams.add(f"{source_team}:{target_team}")
            self._repelled_teams.add(f"{target_team}:{source_team}")
            self._emit_event(TeamRepelledEvent(source_team, target_team))
            self.logger.info("Repulsion established")
            
        self.logger.info("\nCurrent Flow State:")
        self.logger.info(f"Active Flows: {dict(self._flows)}")
        self.logger.info(f"Repelled Teams: {self._repelled_teams}")
        self.logger.info(f"{'='*50}\n")

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
        
    async def attract(self, team1: str, team2: str) -> bool:
        """Attract two teams (bidirectional flow)"""
        self.logger.info(f"\n{'='*20} Team Attraction {'='*20}")
        self.logger.info(f"Team 1: {team1}")
        self.logger.info(f"Team 2: {team2}")
        
        try:
            success = await self.process_team_flow(team1, team2, None, "><")
            if success:
                self.logger.info("Teams attracted successfully")
                self.logger.info(f"Bidirectional flow established between {team1} and {team2}")
            else:
                self.logger.error("Failed to attract teams")
            self.logger.info(f"{'='*50}\n")
            return True
        except ValueError as e:
            self.logger.error(f"Error attracting teams: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            return False
            
    async def repel(self, team1: str, team2: str) -> bool:
        """Repel two teams (no communication)"""
        self.logger.info(f"\n{'='*20} Team Repulsion {'='*20}")
        self.logger.info(f"Team 1: {team1}")
        self.logger.info(f"Team 2: {team2}")
        
        try:
            success = await self.process_team_flow(team1, team2, None, "<>")
            if success:
                self.logger.info("Teams repelled successfully")
                self.logger.info(f"Communication blocked between {team1} and {team2}")
            else:
                self.logger.error("Failed to repel teams")
            self.logger.info(f"{'='*50}\n")
            return True
        except ValueError as e:
            self.logger.error(f"Error repelling teams: {str(e)}")
            self.logger.info(f"{'='*50}\n")
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
        self.logger.info(f"\n{'='*20} Sharing Team Results {'='*20}")
        self.logger.info(f"Source Team: {source_team}")
        self.logger.info(f"Target Team: {target_team}")
        self.logger.info(f"Result Types: {list(results.keys())}")
        
        try:
            # Validate flow exists
            flow_type = self._get_flow_type(source_team, target_team)
            if not flow_type:
                self.logger.error(f"No magnetic flow defined between {source_team} and {target_team}")
                raise ValueError(f"No magnetic flow defined between {source_team} and {target_team}")
            
            self.logger.info(f"\nFlow Type: {flow_type}")
            
            # Log current state
            self.logger.info("\nCurrent Shared Results:")
            self.logger.info(f"Existing Results: {dict(self._shared_results)}")
            
            # Store results
            if source_team not in self._shared_results:
                self._shared_results[source_team] = {}
                self.logger.info(f"Created new results store for {source_team}")
                
            self._shared_results[source_team][target_team] = results
            self.logger.info("Results stored successfully")
            
            # Emit events
            self.logger.info("\nEmitting Events:")
            for result_type in results.keys():
                self.logger.info(f"- Emitting event for: {result_type}")
                self._emit_event(ResultsSharedEvent(source_team, target_team, result_type))
            
            self.logger.info("\nFinal Shared Results State:")
            self.logger.info(f"Updated Results: {dict(self._shared_results)}")
            self.logger.info(f"{'='*50}\n")
            
        except Exception as e:
            self.logger.error(f"Error sharing results: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            raise

    async def enable_field_pull(self, source_field: 'MagneticField') -> bool:
        """Enable pulling from another field"""
        self.logger.info(f"\n{'='*20} Enable Field Pull {'='*20}")
        self.logger.info(f"Target Field: {self.name}")
        self.logger.info(f"Source Field: {source_field.name}")
        self.logger.info(f"Pull Team Status: {self.is_pull_team}")
        
        if not self.is_pull_team:
            self.logger.error("Field is not configured as a pull team")
            return False
            
        try:
            self.logger.info("Setting up field pull flow...")
            success = await self.process_team_flow(self.name, source_field.name, None, "<-")
            if success:
                self.logger.info("Field pull enabled successfully")
                self.logger.info(f"Pull flow established from {source_field.name} to {self.name}")
            else:
                self.logger.error("Failed to enable field pull")
            self.logger.info(f"{'='*50}\n")
            return True
        except ValueError as e:
            self.logger.error(f"Error enabling field pull: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            return False
            
    async def enable_pull(self, target_team: str, source_team: str) -> bool:
        """Enable one-way pull flow from source team to target team"""
        self.logger.info(f"\n{'='*20} Enable Pull Flow {'='*20}")
        self.logger.info(f"Target Team (Puller): {target_team}")
        self.logger.info(f"Source Team: {source_team}")
        
        try:
            success = await self.process_team_flow(target_team, source_team, None, "<-")
            if success:
                self.logger.info("Pull flow enabled successfully")
            else:
                self.logger.error("Failed to enable pull flow")
            self.logger.info(f"{'='*50}\n")
            return True
        except ValueError as e:
            self.logger.error(f"Error enabling pull flow: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            return False

    async def enable_push(self, source_team: str, target_team: str) -> bool:
        """Enable one-way push flow from source team to target team"""
        self.logger.info(f"\n{'='*20} Enable Push Flow {'='*20}")
        self.logger.info(f"Source Team (Pusher): {source_team}")
        self.logger.info(f"Target Team: {target_team}")
        
        try:
            success = await self.process_team_flow(source_team, target_team, None, "->")
            if success:
                self.logger.info("Push flow enabled successfully")
            else:
                self.logger.error("Failed to enable push flow")
            self.logger.info(f"{'='*50}\n")
            return True
        except ValueError as e:
            self.logger.error(f"Error enabling push flow: {str(e)}")
            self.logger.info(f"{'='*50}\n")
            return False
