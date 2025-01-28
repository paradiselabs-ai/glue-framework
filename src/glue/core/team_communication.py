"""Team-to-Team Communication System"""

import asyncio
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from .model import Model
from .team import Team
from .conversation import ConversationManager
from .memory import MemoryManager
from .context import ContextState
from ..magnetic.field import MagneticField
from .logger import get_logger
@dataclass
class TeamFlow:
    """Team-to-team communication flow"""
    source_team: str
    target_team: str
    flow_type: str  # "><", "->", "<-", "<>"
    shared_data: Dict[str, Any] = field(default_factory=dict)
    last_active: Optional[datetime] = None

class TeamCommunicationManager:
    """
    Manages team-to-team communication using magnetic fields.
    
    Features:
    - Magnetic operators for team interactions:
      * >< (Bidirectional): Teams can freely share data
      * -> (Push): Source team pushes data to target team
      * <- (Pull): Target team pulls data from source team
      * <> (Repel): Teams cannot communicate
    
    - Team boundary enforcement:
      * Teams can only communicate through established magnetic flows
      * Flow direction controls data sharing permissions
      * Repelled teams cannot establish any communication
    
    - Data flow control:
      * Teams share data based on magnetic operator rules
      * Flow history tracks all team interactions
      * Clean separation from intra-team communication
    
    Note: This system only handles team-to-team communication.
    For model-to-model chat within teams, use GroupChatManager. (Roo, i made this change because i want to eventually fix the groupchatmanager to include the simplified concepts, while keeping any of the original features that may be useful without overly complicating things. IF the groupchatmanager just needs to be replaced altogether, then lets replace it with simplegroupchatmanager, but after replacing it, renaming it to groupchatmanager. After the framework is fixed and revised to use the better, simpler concepts, i dont want any of the files to be named "simple" as it looks kinda tacky.)
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.teams: Dict[str, Team] = {}
        self.conversation_manager = ConversationManager()
        self.memory_manager = MemoryManager()
        
        # Flow tracking
        self.active_flows: Dict[str, TeamFlow] = {}
        self.flow_history: List[Dict[str, Any]] = []
        
        # Magnetic field for team interactions
        self.field = MagneticField(name)
    
    async def add_team(self, team: Team) -> None:
        """Add a team to the communication system"""
        self.logger.debug(f"Adding team: {team.name}")
        self.teams[team.name] = team
        await self.field.add_resource(team)
    
    async def set_team_flow(
        self,
        source_team: str,
        target_team: str,
        flow_type: str  # "><", "->", "<-", "<>"
    ) -> str:
        """Set up magnetic flow between teams"""
        self.logger.debug(f"Setting up {flow_type} flow: {source_team} -> {target_team}")
        
        if source_team not in self.teams or target_team not in self.teams:
            raise ValueError("Both teams must be in the system")
            
        # Generate flow ID
        flow_id = f"flow_{len(self.active_flows)}_{datetime.now().timestamp()}"
        
        try:
            # Create flow
            flow = TeamFlow(
                source_team=source_team,
                target_team=target_team,
                flow_type=flow_type,
                last_active=datetime.now()
            )
            
            # Set up magnetic flow
            if flow_type == "><":
                await self.field.attract(self.teams[source_team], self.teams[target_team])
            elif flow_type == "->":
                await self.field.enable_push(self.teams[source_team], self.teams[target_team])
            elif flow_type == "<-":
                await self.field.enable_pull(self.teams[target_team], self.teams[source_team])
            elif flow_type == "<>":
                await self.field.repel(self.teams[source_team], self.teams[target_team])
            else:
                raise ValueError(f"Invalid flow type: {flow_type}")
            
            # Add to active flows
            self.active_flows[flow_id] = flow
            
            self.logger.info(f"Set up flow {flow_id} between {source_team} and {target_team}")
            return flow_id
            
        except Exception as e:
            self.logger.error(f"Error setting up flow: {str(e)}")
            # Clean up if needed
            if flow_id in self.active_flows:
                await self.break_flow(flow_id)
            raise
    
    async def share_results(
        self,
        flow_id: str,
        results: Dict[str, Any],
        from_team: str
    ) -> None:
        """Share results between teams based on magnetic flow"""
        self.logger.debug(f"Sharing results in flow {flow_id}")
        
        if flow_id not in self.active_flows:
            raise ValueError(f"Flow {flow_id} not found")
            
        flow = self.active_flows[flow_id]
        
        # Validate flow direction
        if from_team == flow.source_team and flow.flow_type in ["><", "->"]:
            target = flow.target_team
        elif from_team == flow.target_team and flow.flow_type in ["><", "<-"]:
            target = flow.source_team
        else:
            raise ValueError(f"Invalid flow direction for {from_team}")
            
        # Share data between teams
        flow.shared_data.update(results)
        flow.last_active = datetime.now()
        
        # Store in history
        self.flow_history.append({
            'flow_id': flow_id,
            'timestamp': datetime.now().isoformat(),
            'from_team': from_team,
            'target_team': target,
            'data': results
        })
    
    async def break_flow(self, flow_id: str) -> None:
        """Break magnetic flow between teams"""
        self.logger.debug(f"Breaking flow {flow_id}")
        
        if flow_id not in self.active_flows:
            raise ValueError(f"Flow {flow_id} not found")
            
        flow = self.active_flows[flow_id]
        
        try:
            # Break magnetic flow
            source_team = self.teams[flow.source_team]
            target_team = self.teams[flow.target_team]
            
            if flow.flow_type == "><":
                await self.field.break_attraction(source_team, target_team)
            elif flow.flow_type == "->" or flow.flow_type == "<-":
                await self.field.break_flow(source_team, target_team)
            elif flow.flow_type == "<>":
                await self.field.break_repulsion(source_team, target_team)
            
            # Remove from active flows
            del self.active_flows[flow_id]
            
        except Exception as e:
            self.logger.error(f"Error breaking flow: {str(e)}")
            raise
    
    def get_active_flows(self) -> Dict[str, TeamFlow]:
        """Get all active team flows"""
        return self.active_flows.copy()
    
    def get_team_flows(self, team_name: str) -> Dict[str, str]:
        """Get all flows for a team"""
        flows = {}
        for flow in self.active_flows.values():
            if flow.source_team == team_name:
                flows[flow.target_team] = flow.flow_type
            elif flow.target_team == team_name and flow.flow_type in ["><", "<-"]:
                flows[flow.source_team] = "<-" if flow.flow_type == "<-" else "><"
        return flows
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        self.logger.debug("Cleaning up resources")
        try:
            # Break all flows
            for flow_id in list(self.active_flows.keys()):
                await self.break_flow(flow_id)
            
            # Clean up field
            await self.field.cleanup()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            raise