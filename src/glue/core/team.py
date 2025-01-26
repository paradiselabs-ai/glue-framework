"""Team Implementation"""

from typing import Dict, Set, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .types import ToolResult, AdhesiveType
from .state import StateManager

class TeamRole(Enum):
    """Team member roles"""
    LEAD = "lead"
    MEMBER = "member"
 # i dont think we need an "observer"

@dataclass
class TeamMember:
    """Team member with role and permissions"""
    name: str
    role: TeamRole
    tools: Set[str] = field(default_factory=set)
    joined_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

@dataclass
class TeamState:
    """Persistent team state"""
    name: str
    members: Dict[str, TeamMember]
    tools: Set[str]
    shared_results: Dict[str, ToolResult]
    session_results: Dict[str, Dict[str, ToolResult]]
    relationships: Dict[str, AdhesiveType]
    repelled_by: Set[str]
    created_at: datetime
    updated_at: datetime

class Team:
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
    
    def __init__(
        self,
        name: str,
        members: Optional[Dict[str, TeamMember]] = None,
        tools: Optional[Set[str]] = None,
        shared_results: Optional[Dict[str, ToolResult]] = None,
        session_results: Optional[Dict[str, Dict[str, ToolResult]]] = None,
        state_manager: Optional[StateManager] = None
    ):
        self.name = name
        self.members = members or {}
        self.tools = tools or set()
        self.shared_results = shared_results or {}
        self.session_results = session_results or {}
        self._state_manager = state_manager or StateManager()
        
        # Team relationships with adhesive types
        self._relationships: Dict[str, AdhesiveType] = {}
        self._repelled_by: Set[str] = set()
        
        # Timestamps
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        
    async def add_member(
        self,
        model_name: str,
        role: TeamRole = TeamRole.MEMBER,
        tools: Optional[Set[str]] = None
    ) -> None:
        """Add a model to the team with role and tools"""
        if model_name in self.members:
            raise ValueError(f"Model {model_name} is already a team member")
            
        # Validate tools
        if tools:
            invalid_tools = tools - self.tools
            if invalid_tools:
                raise ValueError(f"Invalid tools: {invalid_tools}")
        
        # Create member
        member = TeamMember(
            name=model_name,
            role=role,
            tools=tools or set()
        )
        self.members[model_name] = member
        
        # Update timestamp
        self.updated_at = datetime.now()
        
    async def add_tool(
        self,
        tool_name: str,
        members: Optional[List[str]] = None
    ) -> None:
        """Add a tool and optionally assign to specific members"""
        self.tools.add(tool_name)
        
        # Add tool to specified members or all members if none specified
        target_members = [self.members[m] for m in (members or self.members.keys())]
        for member in target_members:
            member.tools.add(tool_name)
            member.last_active = datetime.now()
            
        # Update timestamp
        self.updated_at = datetime.now()
        
    async def share_result(
        self,
        tool_name: str,
        result: ToolResult,
        adhesive_type: AdhesiveType = AdhesiveType.GLUE
    ) -> None:
        """Share a result with the team based on adhesive type"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        # Store result based on adhesive type
        if adhesive_type == AdhesiveType.GLUE:
            # Permanent storage
            self.shared_results[tool_name] = result
        elif adhesive_type == AdhesiveType.TAPE:
            # Session storage
            if tool_name not in self.session_results:
                self.session_results[tool_name] = {}
            self.session_results[tool_name][datetime.now().isoformat()] = result
        # VELCRO results are not stored, only used immediately
        
        # Update timestamp
        self.updated_at = datetime.now()
        
    async def push_to(
        self,
        target_team: 'Team',
        results: Optional[Dict[str, ToolResult]] = None
    ) -> None:
        """Push results to target team based on relationship"""
        # Validate relationship
        if target_team.name in self._repelled_by:
            raise ValueError(f"Cannot push to {target_team.name} - repelled")
            
        # Check if relationship exists (None = adhesive-agnostic)
        if target_team.name not in self._relationships:
            raise ValueError(f"No relationship with {target_team.name}")
            
        # Share all available results
        if results is None:
            # Share both persistent and session results
            results = {}
            # Add persistent results
            results.update(self.shared_results)
            # Add latest session results
            for tool, sessions in self.session_results.items():
                if sessions:
                    latest = sorted(sessions.items(), key=lambda x: x[0])[-1][1]
                    if tool not in results:  # Don't override persistent results
                        results[tool] = latest
                
        # Share results (let target team handle adhesive type)
        await target_team.receive_results(results)
        
        # Update timestamp
        self.updated_at = datetime.now()
        
    async def pull_from(
        self,
        source_team: 'Team',
        tools: Optional[Set[str]] = None
    ) -> None:
        """Pull specific or all results from source team"""
        # Validate relationship
        if source_team.name in self._repelled_by:
            raise ValueError(f"Cannot pull from {source_team.name} - repelled")
            
        # Check if relationship exists (None = adhesive-agnostic)
        if source_team.name not in self._relationships:
            raise ValueError(f"No relationship with {source_team.name}")
            
        # Request results for specific tools or all tools
        # Let source team share all available results
        await source_team.share_results_with(self, tools)
        
        # Update timestamp
        self.updated_at = datetime.now()
        
    async def receive_results(
        self,
        results: Dict[str, ToolResult],
        adhesive_type: Optional[AdhesiveType] = None
    ) -> None:
        """
        Receive results and store based on team's needs.
        If adhesive_type is None, store based on team's configuration.
        """
        timestamp = datetime.now().isoformat()
        
        for tool_name, result in results.items():
            # Store in persistent storage if using GLUE
            if adhesive_type in (AdhesiveType.GLUE, None):
                self.shared_results[tool_name] = result
                
            # Store in session storage if using TAPE
            if adhesive_type in (AdhesiveType.TAPE, None):
                if tool_name not in self.session_results:
                    self.session_results[tool_name] = {}
                self.session_results[tool_name][timestamp] = result
                
            # VELCRO results are transient - only used immediately
        
        # Update timestamp
        self.updated_at = datetime.now()
        
    async def share_results_with(
        self,
        target_team: 'Team',
        tools: Optional[Set[str]] = None
    ) -> None:
        """Share specific or all results with pulling team"""
        # Share both persistent and session results
        results = {}
        
        # Filter by tools if specified
        sources = [
            (self.shared_results, None),  # Persistent results
            *[(sessions, tool_name) for tool_name, sessions in self.session_results.items()]  # Session results
        ]
        
        for source, tool_name in sources:
            if isinstance(source, dict):
                for name, result in source.items():
                    if tools is None or name in tools:
                        if name not in results:  # Don't override persistent results
                            if tool_name:  # Session results
                                latest = sorted(source.items(), key=lambda x: x[0])[-1][1]
                                results[name] = latest
                            else:  # Persistent results
                                results[name] = result
                
        # Share results (let target team handle adhesive type)
        await target_team.receive_results(results)
        
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
        if team_name in self._repelled_by:
            raise ValueError(f"Cannot set relationship with {team_name} - repelled")
            
        # Store relationship (None = adhesive-agnostic)
        self._relationships[team_name] = adhesive_type
        
        # Update timestamp
        self.updated_at = datetime.now()
        
    def remove_relationship(self, team_name: str) -> None:
        """Remove relationship with a team"""
        if team_name in self._relationships:
            del self._relationships[team_name]
            
        # Update timestamp
        self.updated_at = datetime.now()
        
    def repel(self, team_name: str, bidirectional: bool = False) -> None:
        """Prevent any interaction with a team"""
        self._repelled_by.add(team_name)
        # Remove any existing relationship
        if team_name in self._relationships:
            del self._relationships[team_name]
            
        # Update timestamp
        self.updated_at = datetime.now()
        
    def save_state(self) -> TeamState:
        """Save team state for persistence"""
        return TeamState(
            name=self.name,
            members=self.members,
            tools=self.tools,
            shared_results=self.shared_results,
            session_results=self.session_results,
            relationships=self._relationships,
            repelled_by=self._repelled_by,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
        
    @classmethod
    def load_state(cls, state: TeamState) -> 'Team':
        """Load team state from persistence"""
        team = cls(
            name=state.name,
            members=state.members,
            tools=state.tools,
            shared_results=state.shared_results,
            session_results=state.session_results
        )
        
        # Restore relationships
        team._relationships = state.relationships
        team._repelled_by = state.repelled_by
        
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
