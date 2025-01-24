# src/glue/core/model.py
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from .types import Message, MessageType, WorkflowState, IntentAnalysis
from ..tools.base import BaseTool
from .tool_binding import ToolBinding, AdhesiveType, ToolBindingState

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
        
        # Team communication
        self._attracted_to: Set[str] = set()  # Models we can chat with
        self._repelled_by: Set[str] = set()   # Models we can't chat with

    def set_role(self, role: str) -> None:
        """Set the model's role"""
        self.role = role
        if not self.config.system_prompt:
            self.config.system_prompt = role

    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use a tool with specified adhesive type"""
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
        
        # Handle result based on adhesive
        if adhesive == AdhesiveType.VELCRO:
            self._session_results[tool_name] = tool_result
            
        return tool_result

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
        """Process a received message (to be implemented by provider)"""
        raise NotImplementedError
        
    async def generate(self, prompt: str) -> str:
        """Generate a response (to be implemented by provider)"""
        raise NotImplementedError
