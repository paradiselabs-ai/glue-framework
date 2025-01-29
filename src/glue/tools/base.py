"""GLUE Tool Base System"""

import asyncio
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto

from ..core.types import AdhesiveType
from ..core.logger import get_logger

# ==================== Tool Permissions ====================
class ToolPermission(Enum):
    """Tool permissions for documentation and validation"""
    READ = auto()        # Read access to resources
    WRITE = auto()       # Write access to resources
    NETWORK = auto()     # Network access
    FILE_SYSTEM = auto() # File system access
    EXECUTE = auto()     # Code execution

# ==================== Tool Configuration ====================
@dataclass
class ToolConfig:
    """Configuration for a tool"""
    timeout: float = 30.0
    async_enabled: bool = True
    tool_specific_config: Dict[str, Any] = field(default_factory=dict)
    required_permissions: List[ToolPermission] = field(default_factory=list)

# ==================== Tool States ====================
class ToolState(Enum):
    """Tool execution states"""
    IDLE = "idle"      # Tool is ready for use
    ACTIVE = "active"  # Tool is currently executing

# ==================== Base Tool ====================
class BaseTool(ABC):
    """
    Base class for all GLUE tools.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Adhesive-based persistence (TAPE/VELCRO/GLUE)
    - Basic error handling
    - Async context management
    - Input validation
    """
    def __init__(
        self,
        name: str,
        description: str,
        adhesive_type: Optional[AdhesiveType] = None,
        config: Optional[ToolConfig] = None,
        tags: Optional[set[str]] = None
    ):
        # Initialize core components
        self.name = name
        self.description = description
        self.adhesive_type = adhesive_type or AdhesiveType.TAPE
        self.tags = tags or {name, "tool"}  # Basic categorization
        
        # Tool configuration
        self.config = config or ToolConfig()
        self._is_initialized = False
        self._last_result = None  # For VELCRO/GLUE persistence
        
        # Initialize state
        self.state = ToolState.IDLE
        
        # Initialize logger
        self.logger = get_logger()

    @abstractmethod
    async def _execute(self, *args, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass

    @abstractmethod
    async def _validate_input(self, *args, **kwargs) -> bool:
        """Validate tool input. Override in subclass."""
        return True

    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with state tracking and result persistence"""
        # Check for persisted results first
        if self.adhesive_type != AdhesiveType.TAPE and self._last_result:
            return self._last_result
            
        # Validate input
        if not await self._validate_input(*args, **kwargs):
            raise ValueError("Invalid tool input")
            
        # Transition to ACTIVE
        self.state = ToolState.ACTIVE
        
        try:
            # Initialize if needed
            if not self._is_initialized:
                await self.initialize()
                
            # Execute tool
            result = await self._execute(*args, **kwargs)
            
            # Store result based on adhesive type
            if self.adhesive_type != AdhesiveType.TAPE:
                self._last_result = result
            
            return result
            
        finally:
            # Always return to IDLE
            self.state = ToolState.IDLE

    async def initialize(self) -> None:
        """Initialize tool resources"""
        self._is_initialized = True

    async def cleanup(self) -> None:
        """Clean up resources based on adhesive type"""
        self._is_initialized = False
        self.state = ToolState.IDLE
        
        # Clear results based on adhesive type
        if self.adhesive_type != AdhesiveType.GLUE:
            self._last_result = None

    async def __aenter__(self) -> 'BaseTool':
        """Async context manager entry"""
        if not self._is_initialized:
            await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        await self.cleanup()

    def __str__(self) -> str:
        """String representation with adhesive type"""
        return f"{self.name}: {self.description} ({self.adhesive_type.name})"
