"""Team Implementation with Pydantic Models"""

from typing import Dict, Set, Any, Optional, List
from datetime import datetime
from enum import Enum
from prefect import task, flow
from pydantic import BaseModel, Field

from .types import ToolResult, AdhesiveType
from .state import StateManager
from .tool_binding import ToolBinding
from ..tools.base import BaseTool
from .model import Model
from .logger import get_logger
from .pydantic_models import TeamContext, ModelState, SmolAgentsTool

logger = get_logger("team")

class TeamRole(str, Enum):
    """Team member roles"""
    LEAD = "lead"
    MEMBER = "member"

class TeamMember(BaseModel):
    """Team member with role and permissions"""
    name: str
    role: TeamRole
    tools: Set[str] = Field(default_factory=set)
    joined_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)

class TeamState(BaseModel):
    """Persistent team state"""
    name: str
    members: Dict[str, TeamMember]
    tools: Set[str]
    shared_results: Dict[str, ToolResult]  # Only GLUE results
    relationships: Dict[str, AdhesiveType]
    repelled_by: Set[str]
    created_at: datetime
    updated_at: datetime

class Team(BaseModel):
    """
    Team implementation with advanced functionality.
    
    Features:
    - Role-based member management
    - Tool access control
    - Result sharing based on adhesive type
    - Magnetic flow between teams
    - State persistence with history
    - Resource management with validation
    """
    name: str
    models: Dict[str, ModelState] = Field(default_factory=dict)
    members: Dict[str, TeamMember] = Field(default_factory=dict)
    tools: Dict[str, SmolAgentsTool] = Field(default_factory=dict)
    tool_bindings: Dict[str, ToolBinding] = Field(default_factory=dict)
    context: TeamContext = Field(default_factory=TeamContext)
    relationships: Dict[str, AdhesiveType] = Field(default_factory=dict)
    repelled_by: Set[str] = Field(default_factory=set)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True

    async def add_member(
        self,
        model_name: str,
        role: TeamRole = TeamRole.MEMBER,
        tools: Optional[Set[str]] = None
    ) -> None:
        """Add a model to the team with role and tools"""
        if model_name in self.members:
            raise ValueError(f"Model {model_name} is already a team member")
            
        # Get model instance
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        model = self.models[model_name]
        
        # Give model access to team's tools
        for tool_name, tool in self.tools.items():
            model._tools[tool_name] = tool
        
        # Create member
        member = TeamMember(
            name=model_name,
            role=role,
            tools=set(self.tools.keys())  # Give access to all team tools
        )
        self.members[model_name] = member
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Added member {model_name} to team {self.name}")

    async def add_tool(
        self,
        tool: SmolAgentsTool,
        members: Optional[List[str]] = None
    ) -> None:
        """Add a tool and optionally assign to specific members"""
        # Add tool instance
        self.tools[tool.name] = tool
        
        # Add tool to all team members' models
        for member_name in self.members:
            if member_name in self.models:
                model = self.models[member_name]
                model._tools[tool.name] = tool
                self.members[member_name].tools.add(tool.name)
                self.members[member_name].last_active = datetime.now()
            
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Added tool {tool.name} to team {self.name}")

    async def share_result(
        self,
        tool_name: str,
        result: ToolResult,
        adhesive_type: AdhesiveType = AdhesiveType.GLUE
    ) -> None:
        """Share a result with the team based on adhesive type"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        binding = self.tool_bindings.get(tool_name)
        if not binding:
            binding = ToolBinding.glue()
            binding.bind()
            self.tool_bindings[tool_name] = binding
            
        # Store result based on binding type
        if adhesive_type == AdhesiveType.GLUE:
            # Permanent team-wide storage
            self.context.shared_results[tool_name] = result
        elif adhesive_type == AdhesiveType.VELCRO:
            # Session storage in binding
            binding.store_resource(tool_name, result)
        # TAPE results are not stored
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Shared {tool_name} result in team {self.name}")

    async def push_to(
        self,
        target_team: "Team",  # Use string literal for forward reference
        results: Optional[Dict[str, ToolResult]] = None
    ) -> None:
        """Push results to target team based on relationship"""
        # Validate relationship
        if target_team.name in self.repelled_by:
            raise ValueError(f"Cannot push to {target_team.name} - repelled")
            
        # Check if relationship exists
        if target_team.name not in self.relationships:
            raise ValueError(f"No relationship with {target_team.name}")
            
        # Share all available GLUE results if none specified
        if results is None:
            results = self.context.shared_results.copy()
                
        # Share results (let target team handle adhesive type)
        await target_team.receive_results(results)
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Pushed results to team {target_team.name}")

    async def pull_from(
        self,
        source_team: "Team",  # Use string literal for forward reference
        tools: Optional[Set[str]] = None
    ) -> None:
        """Pull specific or all results from source team"""
        # Validate relationship
        if source_team.name in self.repelled_by:
            raise ValueError(f"Cannot pull from {source_team.name} - repelled")
            
        # Check if relationship exists
        if source_team.name not in self.relationships:
            raise ValueError(f"No relationship with {source_team.name}")
            
        # Request results for specific tools or all tools
        await source_team.share_results_with(self, tools)
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Pulled results from team {source_team.name}")

    async def receive_results(
        self,
        results: Dict[str, ToolResult],
        adhesive_type: Optional[AdhesiveType] = None
    ) -> None:
        """
        Receive results and store based on team's needs.
        If adhesive_type is None, store based on team's configuration.
        """
        for tool_name, result in results.items():
            # Only store in shared_results if using GLUE
            if adhesive_type in (AdhesiveType.GLUE, None):
                self.context.shared_results[tool_name] = result
            # VELCRO results stay in tool instance
            # TAPE results are not stored
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Received {len(results)} results in team {self.name}")

    async def share_results_with(
        self,
        target_team: "Team",  # Use string literal for forward reference
        tools: Optional[Set[str]] = None
    ) -> None:
        """Share specific or all results with pulling team"""
        # Only share GLUE results
        results = {}
        for name, result in self.context.shared_results.items():
            if tools is None or name in tools:
                results[name] = result
                
        # Share results (let target team handle adhesive type)
        await target_team.receive_results(results)
        logger.info(f"Shared results with team {target_team.name}")

    async def send_message(
        self,
        sender: str,
        receiver: str,
        content: Any,
        adhesive_type: AdhesiveType = AdhesiveType.VELCRO
    ) -> None:
        """Send a message between team members"""
        # Validate members
        if sender not in self.members:
            raise ValueError(f"Sender {sender} is not a team member")
        if receiver not in self.members:
            raise ValueError(f"Receiver {receiver} is not a team member")
            
        # Update member activity
        self.members[sender].last_active = datetime.now()
        self.members[receiver].last_active = datetime.now()
        
        # Message passing handled by communication system
        # This just validates and updates state
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Sent message from {sender} to {receiver} in team {self.name}")

    def set_relationship(
        self,
        team_name: str,
        adhesive_type: Optional[AdhesiveType],
        bidirectional: bool = False
    ) -> None:
        """
        Set relationship with another team.
        If adhesive_type is None, relationship is adhesive-agnostic.
        """
        if team_name in self.repelled_by:
            raise ValueError(f"Cannot set relationship with {team_name} - repelled")
            
        # Store relationship (None = adhesive-agnostic)
        self.relationships[team_name] = adhesive_type
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Set relationship with team {team_name}")

    def remove_relationship(self, team_name: str) -> None:
        """Remove relationship with a team"""
        if team_name in self.relationships:
            del self.relationships[team_name]
            
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Removed relationship with team {team_name}")

    def repel(self, team_name: str, bidirectional: bool = False) -> None:
        """Prevent any interaction with a team"""
        self.repelled_by.add(team_name)
        # Remove any existing relationship
        if team_name in self.relationships:
            del self.relationships[team_name]
            
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Set repulsion with team {team_name}")

    def save_state(self) -> TeamState:
        """Save team state for persistence"""
        return TeamState(
            name=self.name,
            members=self.members,
            tools=set(self.tools.keys()),
            shared_results=self.context.shared_results,
            relationships=self.relationships,
            repelled_by=self.repelled_by,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def load_state(cls, state: TeamState) -> 'Team':
        """Load team state from persistence"""
        team = cls(
            name=state.name,
            members=state.members,
            tools={},  # Tools need to be re-added
            context=TeamContext(shared_results=state.shared_results)
        )
        
        # Restore relationships
        team.relationships = state.relationships
        team.repelled_by = state.repelled_by
        
        # Restore timestamps
        team.created_at = state.created_at
        team.updated_at = state.updated_at
        
        return team

    def get_member_tools(self, member_name: str) -> Set[str]:
        """Get tools available to a member"""
        if member_name not in self.members:
            raise ValueError(f"Unknown member: {member_name}")
        return self.members[member_name].tools

    def get_active_members(self, since: Optional[datetime] = None) -> List[TeamMember]:
        """Get members active since given time"""
        if since is None:
            return list(self.members.values())
            
        return [
            member for member in self.members.values()
            if member.last_active >= since
        ]

    def get_member_role(self, member_name: str) -> TeamRole:
        """Get a member's role"""
        if member_name not in self.members:
            raise ValueError(f"Unknown member: {member_name}")
        return self.members[member_name].role

    @property
    def lead(self) -> Optional[str]:
        """Get the team's lead model name"""
        for name, member in self.members.items():
            if member.role == TeamRole.LEAD:
                return name
        return None

    def get_team_flows(self) -> Dict[str, str]:
        """Get magnetic flows with other teams"""
        flows = {}
        for team_name, adhesive in self.relationships.items():
            if team_name not in self.repelled_by:
                # Convert relationship to magnetic operator
                if team_name in self.repelled_by:
                    flows[team_name] = "<>"  # Repulsion
                else:
                    # Check if bidirectional
                    if team_name in self.relationships and self.name in self.relationships.get(team_name, {}):
                        flows[team_name] = "><"  # Bidirectional
                    else:
                        flows[team_name] = "->"  # Push by default
        return flows

    def update_member_role(
        self,
        member_name: str,
        new_role: TeamRole,
        by_member: Optional[str] = None
    ) -> None:
        """Update a member's role"""
        # Validate members
        if member_name not in self.members:
            raise ValueError(f"Unknown member: {member_name}")
        if by_member and by_member not in self.members:
            raise ValueError(f"Unknown member: {by_member}")
            
        # Only leads can change roles
        if by_member and self.members[by_member].role != TeamRole.LEAD:
            raise ValueError("Only team leads can change roles")
            
        # Update role
        self.members[member_name].role = new_role
        self.members[member_name].last_active = datetime.now()
        
        # Update timestamp
        self.updated_at = datetime.now()
        logger.info(f"Updated role for member {member_name} to {new_role}")

# Add Prefect decorators after class definition
Team.add_member = task(Team.add_member)
Team.add_tool = task(Team.add_tool)
Team.share_result = flow(name="share_result")(Team.share_result)
Team.push_to = flow(name="push_to_team")(Team.push_to)
Team.pull_from = flow(name="pull_from_team")(Team.pull_from)
Team.receive_results = task(Team.receive_results)
Team.share_results_with = task(Team.share_results_with)
Team.send_message = task(Team.send_message)
