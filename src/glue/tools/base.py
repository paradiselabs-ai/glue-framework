"""GLUE Tool Base System"""

import asyncio
from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from ..core.types import AdhesiveType
from ..core.logger import get_logger

# ==================== Tool Configuration ====================
import warnings

@dataclass
class ToolConfig:
    """Configuration for a tool"""
    max_retries: int = 3
    timeout: float = 30.0
    cache_results: bool = False
    async_enabled: bool = True
    
    def __post_init__(self):
        # For backward compatibility
        if hasattr(self, 'required_permissions'):
            warnings.warn(
                "Tool permissions system has been deprecated and will be removed. "
                "Use adhesive types for managing tool persistence and access.",
                DeprecationWarning,
                stacklevel=2
            )

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
    - Error handling
    - Safe execution
    - Instance management
    """
    def __init__(
        self,
        name: str,
        description: str,
        adhesive_type: Optional[AdhesiveType] = None,
        config: Optional[ToolConfig] = None
    ):
        # Initialize core components
        self.name = name
        self.description = description
        self.adhesive_type = adhesive_type or AdhesiveType.TAPE
        
        # Tool configuration
        self.config = config or ToolConfig()
        self._error_handlers: Dict[type, callable] = {}
        self._is_initialized = False
        self._instance_data: Dict[str, Any] = {}
        self._last_result = None  # For VELCRO/GLUE persistence
        
        # Initialize state
        self.state = ToolState.IDLE
        
        # Initialize logger
        self.logger = get_logger()

    @abstractmethod
    async def _execute(self, *args, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass

    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with state tracking and result persistence"""
        # Check for persisted results first
        if self.adhesive_type != AdhesiveType.TAPE and self._last_result:
            return self._last_result
            
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
            
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}")
            raise
            
        finally:
            # Always return to IDLE
            self.state = ToolState.IDLE

    async def initialize(self, instance_data: Optional[Dict[str, Any]] = None) -> None:
        """Initialize tool resources"""
        if instance_data:
            self._instance_data.update(instance_data)
        self._is_initialized = True
        
    def create_instance(self, adhesive_type: Optional[AdhesiveType] = None) -> 'BaseTool':
        """Create a new instance of this tool with shared configuration"""
        instance = self.__class__(
            name=self.name,
            description=self.description,
            adhesive_type=adhesive_type or self.adhesive_type,
            config=self.config
        )
        return instance
        
    def create_isolated_instance(self) -> 'BaseTool':
        """Create an isolated instance with no shared data"""
        instance = self.create_instance()
        instance._instance_data = {}  # Empty instance data
        return instance

    async def cleanup(self) -> None:
        """Clean up resources based on adhesive type"""
        self._is_initialized = False
        self.state = ToolState.IDLE
        
        # Clear results based on adhesive type
        if self.adhesive_type != AdhesiveType.GLUE:
            self._last_result = None

    def add_error_handler(self, error_type: type, handler: callable) -> None:
        """Add error handler for specific error types"""
        self._error_handlers[error_type] = handler

    async def safe_execute(self, *args, **kwargs) -> Any:
        """Execute with error handling"""
        try:
            return await self.execute(*args, **kwargs)
        except Exception as e:
            error_type = type(e)
            handler = self._error_handlers.get(error_type)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(e)
                return handler(e)
            raise

    def __str__(self) -> str:
        """String representation with adhesive type"""
        return f"{self.name}: {self.description} ({self.adhesive_type.name})"
