# src/glue/core/model.py
from typing import Dict, Any, Optional, List, Set, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from .types import IntentAnalysis, AdhesiveType, ToolResult

if TYPE_CHECKING:
    from ..tools.base import BaseTool
    from .tool_binding import ToolBinding

@dataclass
class ModelConfig:
    """Configuration for a model"""
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop_sequences: list[str] = field(default_factory=list)
    system_prompt: Optional[str] = None

class Model:
    """Base class for models that can use tools and communicate"""
    def __init__(
        self, 
        name: str,
        provider: str,
        team: str,
        available_adhesives: Set[AdhesiveType],
        api_key: Optional[str] = None,
        config: Optional[ModelConfig] = None
    ):
        self.name = name
        self.provider = provider
        self.team = team
        self.available_adhesives = available_adhesives
        self.api_key = api_key
        self.config = config or ModelConfig()
        self.role: Optional[str] = None
        
        # Tool management
        self._tools: Dict[str, Any] = {}
        self._session_results: Dict[str, ToolResult] = {}  # VELCRO results
        self._tool_history: List[Dict[str, Any]] = []  # Track tool usage
        
        # Team communication
        self._attracted_to: Set[str] = set()  # Models we can chat with
        self._repelled_by: Set[str] = set()   # Models we can't chat with
        self._conversation_history: List[Dict[str, Any]] = []  # Track interactions
        self._team_context: Dict[str, Any] = {}  # Shared team knowledge

    def set_role(self, role: str) -> None:
        """Set the model's role"""
        self.role = role
        if not self.config.system_prompt:
            self.config.system_prompt = role

    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use tools naturally like office tools"""
        # Track tool usage
        self._tool_history.append({
            "tool": tool_name,
            "adhesive": adhesive,
            "input": input_data,
            "timestamp": datetime.now()
        })
        if adhesive not in self.available_adhesives:
            raise ValueError(f"Model {self.name} cannot use {adhesive.name} adhesive")
            
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not available")
            
        # Execute tool
        tool = self._tools[tool_name]
        result = await tool.execute(input_data)
        
        # Create tool result
        tool_result = ToolResult(
            tool_name=tool_name,
            result=result,
            adhesive=adhesive,
            timestamp=datetime.now()
        )
        
        # Handle result based on adhesive (like storing files)
        if adhesive == AdhesiveType.GLUE:
            # Store in team's shared drive
            if hasattr(self, 'team') and hasattr(self.team, 'shared_results'):
                self.team.shared_results[tool_name] = tool_result
                # Update team context
                self._team_context[f"{tool_name}_result"] = tool_result
        elif adhesive == AdhesiveType.VELCRO:
            # Store in personal workspace
            self._session_results[tool_name] = tool_result
        # TAPE results are temporary
        
        # Update tool history with result
        self._tool_history[-1]["result"] = tool_result
            
        return tool_result

    def _store_interaction(self, content: Any, interaction_type: str = "message") -> None:
        """Store an interaction in conversation history"""
        self._conversation_history.append({
            "type": interaction_type,
            "content": content,
            "timestamp": datetime.now(),
            "team": self.team,
            "tools_used": [t["tool"] for t in self._tool_history[-3:]]  # Last 3 tools used
        })

    def _get_relevant_context(self) -> Dict[str, Any]:
        """Get relevant context from history and team"""
        # Get recent interactions
        recent_history = self._conversation_history[-3:]  # Last 3 interactions
        
        # Get recent tool usage
        recent_tools = self._tool_history[-3:]  # Last 3 tool uses
        
        # Get team context
        team_info = {
            "name": self.team,
            "shared_knowledge": self._team_context
        }
        
        # Add shared results if available
        if hasattr(self, 'team') and hasattr(self.team, 'shared_results'):
            team_info["shared_results"] = self.team.shared_results
            
        return {
            "recent_history": recent_history,
            "recent_tools": recent_tools,
            "team": team_info
        }

    def _get_available_tools(self) -> List[str]:
        """Get list of available tools"""
        return list(self._tools.keys())

    async def process(self, prompt: str) -> str:
        """Process a prompt naturally like a team member would"""
        # Store the interaction
        self._store_interaction(prompt)
        
        # Consider the context naturally
        context = self._get_relevant_context()
        
        # Think about available tools
        available_tools = self._get_available_tools()
        
        # Generate response with natural thinking
        return await self.generate(prompt)

    async def send_message(self, receiver: str, content: Any) -> None:
        """Send a message to another model"""
        if receiver in self._repelled_by:
            raise ValueError(f"Cannot send message to {receiver} - repelled")
            
        # Message sending handled by Team class
        await self.team.send_message(self.name, receiver, content)
        
    async def receive_message(self, sender: str, content: Any) -> None:
        """Receive a message from another model"""
        if sender in self._repelled_by:
            raise ValueError(f"Cannot receive message from {sender} - repelled")
            
        # Process message (to be implemented by provider)
        await self.process_message(sender, content)
        
    async def process_message(self, sender: str, content: Any) -> None:
        """Process a received message from another team member"""
        if isinstance(content, dict) and content.get('type') == 'tool_result':
            # Store tool result in shared results if using GLUE
            tool_name = content.get('tool')
            result = content.get('result')
            if tool_name and result:
                tool_result = ToolResult(
                    tool_name=tool_name,
                    result=result,
                    adhesive=AdhesiveType.GLUE,
                    timestamp=datetime.now()
                )
                if hasattr(self, 'team') and hasattr(self.team, 'shared_results'):
                    self.team.shared_results[tool_name] = tool_result
                    # Update team context
                    self._team_context[f"{tool_name}_result"] = tool_result
        
    async def generate(self, prompt: str) -> str:
        """Generate a response (to be implemented by provider)"""
        raise NotImplementedError
