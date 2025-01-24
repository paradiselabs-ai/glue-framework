"""Team Implementation for GLUE Framework"""

from typing import Dict, Set, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .types import ToolResult

class Team:
    """
    Team of models that can collaborate and share results.
    
    Features:
    - Free communication between team members
    - Result sharing based on adhesive type
    - Magnetic flow between teams
    """
    
    def __init__(self, name: str):
        self.name = name
        self.members: Set[str] = set()
        self.tools: Set[str] = set()
        
        # Result storage
        self.shared_results: Dict[str, ToolResult] = {}  # GLUE results shared by team
        
        # Team relationships
        self._can_push_to: Set[str] = set()    # Teams we can push to
        self._can_pull_from: Set[str] = set()  # Teams we can pull from
        self._repelled_by: Set[str] = set()    # Teams we can't interact with
        
    async def add_member(self, model_name: str) -> None:
        """Add a model to the team"""
        self.members.add(model_name)
        
    async def add_tool(self, tool_name: str) -> None:
        """Add a tool that team members can use"""
        self.tools.add(tool_name)
        
    async def share_result(self, tool_name: str, result: ToolResult) -> None:
        """Share a GLUE-level result with the team"""
        self.shared_results[tool_name] = result
        
    async def push_to(self, target_team: 'Team') -> None:
        """Push shared results to target team"""
        if target_team.name in self._repelled_by:
            raise ValueError(f"Cannot push to {target_team.name} - repelled")
            
        if target_team.name not in self._can_push_to:
            raise ValueError(f"Not configured to push to {target_team.name}")
            
        # Share all GLUE-level results
        await target_team.receive_results(self.shared_results)
        
    async def pull_from(self, source_team: 'Team') -> None:
        """Pull results from source team"""
        if source_team.name in self._repelled_by:
            raise ValueError(f"Cannot pull from {source_team.name} - repelled")
            
        if source_team.name not in self._can_pull_from:
            raise ValueError(f"Not configured to pull from {source_team.name}")
            
        # Get all shareable results
        await source_team.share_results_with(self)
        
    async def receive_results(self, results: Dict[str, ToolResult]) -> None:
        """Receive results pushed from another team"""
        # Add results to shared storage
        self.shared_results.update(results)
        
    async def share_results_with(self, target_team: 'Team') -> None:
        """Share results with a team that's pulling"""
        # Share all GLUE-level results
        await target_team.receive_results(self.shared_results)
        
    async def send_message(self, sender: str, receiver: str, content: Any) -> None:
        """Send a message between team members"""
        if sender not in self.members:
            raise ValueError(f"Sender {sender} is not a team member")
            
        if receiver not in self.members:
            raise ValueError(f"Receiver {receiver} is not a team member")
            
        # Message passing handled by communication system
        # This just verifies the members can communicate
        
    def allow_push_to(self, team_name: str) -> None:
        """Allow pushing results to a team"""
        self._can_push_to.add(team_name)
        
    def allow_pull_from(self, team_name: str) -> None:
        """Allow pulling results from a team"""
        self._can_pull_from.add(team_name)
        
    def repel(self, team_name: str) -> None:
        """Prevent any interaction with a team"""
        self._repelled_by.add(team_name)
        # Remove any existing permissions
        self._can_push_to.discard(team_name)
        self._can_pull_from.discard(team_name)
        
    def save_state(self) -> Dict[str, Any]:
        """Save team state for persistence"""
        return {
            "name": self.name,
            "members": list(self.members),
            "tools": list(self.tools),
            "shared_results": {
                name: result.__dict__ 
                for name, result in self.shared_results.items()
            }
        }
        
    @classmethod
    def load_state(cls, state: Dict[str, Any]) -> 'Team':
        """Load team state from persistence"""
        team = cls(state["name"])
        team.members = set(state["members"])
        team.tools = set(state["tools"])
        
        # Reconstruct tool results
        for name, result_dict in state["shared_results"].items():
            team.shared_results[name] = ToolResult(**result_dict)
            
        return team
