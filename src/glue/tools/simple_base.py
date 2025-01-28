"""Simplified GLUE Tool Base System"""

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from ..core.simple_resource import SimpleResource
from ..core.state import ResourceState
from ..core.types import AdhesiveType

class SimpleBaseTool(SimpleResource, ABC):
    """
    Simplified base class for all GLUE tools.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Adhesive-based persistence (TAPE/VELCRO/GLUE)
    - Clean initialization
    """
    def __init__(
        self,
        name: str,
        description: str,
        adhesive_type: Optional[AdhesiveType] = None
    ):
        # Initialize base resource
        super().__init__(
            name=name,
            category="tool",
            tags={"tool", name}
        )
        
        # Tool-specific attributes
        self.description = description
        self.adhesive_type = adhesive_type or AdhesiveType.TAPE
        self._is_initialized = False
        self.state = ResourceState.IDLE
        self._last_result = None  # For VELCRO/GLUE persistence
    
    @abstractmethod
    async def _execute(self, *args, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass
    
    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with simple state tracking"""
        # Check for persisted results first
        if self.adhesive_type != AdhesiveType.TAPE and self._last_result:
            return self._last_result
            
        # Transition to ACTIVE
        self.state = ResourceState.ACTIVE
        
        try:
            # Initialize if needed
            if not self._is_initialized:
                await self.initialize()
                
            # Execute and store result based on adhesive type
            result = await self._execute(*args, **kwargs)
            if self.adhesive_type != AdhesiveType.TAPE:
                self._last_result = result
                
            return result
            
        finally:
            # Always return to IDLE
            self.state = ResourceState.IDLE
    
    async def initialize(self) -> None:
        """Initialize tool resources"""
        self._is_initialized = True
    
    async def cleanup(self) -> None:
        """Clean up resources based on adhesive type"""
        self._is_initialized = False
        self.state = ResourceState.IDLE
        
        # Clear results based on adhesive type
        if self.adhesive_type != AdhesiveType.GLUE:
            self._last_result = None
    
    def __str__(self) -> str:
        """String representation with adhesive type"""
        return f"{self.name}: {self.description} ({self.adhesive_type.name})"
