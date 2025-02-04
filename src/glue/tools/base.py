"""Base tool implementation using SmolAgents"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum, auto
from smolagents import Tool

class ToolPermission(Enum):
    """Tool permissions"""
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    FILE_SYSTEM = auto()
    NETWORK = auto()

@dataclass
class ToolConfig:
    """Tool configuration"""
    required_permissions: List[ToolPermission]
    tool_specific_config: Dict[str, Any] = None

class BaseTool(Tool):
    """Base class for all GLUE tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.inputs = {
            "input": {
                "type": "string",
                "description": "Input for the tool"
            }
        }
        self.output_type = "string"
        
    async def forward(self, **kwargs) -> str:
        """Execute the tool with the given input"""
        # This should be overridden by subclasses
        raise NotImplementedError
        
    async def execute(self, input_data: Any) -> str:
        """Execute the tool with proper input validation"""
        # Convert input to expected format
        if isinstance(input_data, dict):
            kwargs = input_data
        else:
            kwargs = {"input": str(input_data)}
            
        # Execute through forward method
        return await self.forward(**kwargs)
