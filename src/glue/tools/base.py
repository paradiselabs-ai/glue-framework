"""Base tool implementation using SmolAgents with enhanced validation and logging"""

from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum, auto
from pydantic import BaseModel, Field
from loguru import logger
from smolagents import Tool

class ToolPermission(Enum):
    """Tool permissions"""
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    FILE_SYSTEM = auto()
    NETWORK = auto()

class ToolConfig(BaseModel):
    """Tool configuration with validation"""
    required_permissions: List[ToolPermission]
    tool_specific_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timeout: float = Field(default=30.0, description="Tool execution timeout in seconds")
    retry_count: int = Field(default=3, description="Number of retry attempts")
    cache_results: bool = Field(default=True, description="Whether to cache tool results")

class ToolData(BaseModel):
    """Validated tool input/output data"""
    input_data: str = Field(..., description="Primary input for the tool")
    params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")

class BaseTool(Tool):
    """Base class for all GLUE tools"""
    
    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        # Initialize SmolAgents Tool first
        super().__init__()
        
        # Set tool name if provided, otherwise use class attribute
        self.name = name or getattr(self, 'name', self.__class__.__name__)
        
        # Set description if not already set by class
        if not hasattr(self, 'description'):
            self.description = getattr(self, 'tool_description', "Base GLUE tool")
        
        # Add validated config wrapper
        self.config = ToolConfig(**(config or {}))
        
        # Set up SmolAgents interface if not already set by class
        if not hasattr(self, 'inputs'):
            self.inputs = {
                "input_data": {
                    "type": "string",
                    "description": "Primary input for the tool"
                },
                "params": {
                    "type": "object",
                    "description": "Additional parameters",
                    "optional": True,
                    "nullable": True,
                    "default": None
                }
            }
        if not hasattr(self, 'output_type'):
            self.output_type = "string"
        
        logger.debug(f"Initialized tool {self.name} with config: {self.config}")
        
    async def forward(self, **kwargs) -> str:
        """Execute the tool with the given input"""
        # This should be overridden by subclasses
        raise NotImplementedError
        
    async def execute(self, input_data: Union[str, Dict[str, Any]]) -> str:
        """Execute the tool with validation, logging, and retry logic while maintaining SmolAgents compatibility"""
        try:
            # Validate input using Pydantic
            if isinstance(input_data, dict):
                validated_data = ToolData(**input_data)
            else:
                validated_data = ToolData(input_data=str(input_data))
            
            logger.debug(f"Executing {self.name} with validated data: {validated_data}")
            
            # Execute with retry logic
            for attempt in range(self.config.retry_count):
                try:
                    result = await self.forward(
                        input_data=validated_data.input_data,
                        **validated_data.params
                    )
                    logger.debug(f"{self.name} execution successful")
                    return result
                except Exception as e:
                    if attempt < self.config.retry_count - 1:
                        logger.warning(f"{self.name} attempt {attempt + 1} failed: {str(e)}")
                        continue
                    raise
                    
        except Exception as e:
            logger.error(f"{self.name} execution failed: {str(e)}")
            raise
