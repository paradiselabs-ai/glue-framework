"""Simplified GLUE Tool Base System"""

import asyncio
from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from ..core.simple_resource import SimpleResource
from ..core.state import ResourceState, StateManager

# ==================== Enums ====================
class ToolPermission(Enum):
    """Permissions that can be granted to tools"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    SYSTEM = "system"

# ==================== Tool Configuration ====================
@dataclass
class ToolConfig:
    """Configuration for a tool"""
    required_permissions: List[ToolPermission]
    max_retries: int = 3
    timeout: float = 30.0
    cache_results: bool = False
    async_enabled: bool = True

# ==================== Base Tool ====================
class SimpleBaseTool(SimpleResource, ABC):
    """
    Simplified base class for all GLUE tools.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Permission system
    - Error handling
    - Safe execution
    """
    def __init__(
        self,
        name: str,
        description: str,
        config: Optional[ToolConfig] = None,
        permissions: Optional[Set[str]] = None,
        sticky: bool = False
    ):
        # Initialize base resource
        super().__init__(
            name=name,
            category="tool",
            tags={"tool", name}
        )
        
        # Tool-specific attributes
        self.description = description
        self.config = config or ToolConfig(required_permissions=[])
        self.permissions = permissions or set()
        self._error_handlers: Dict[type, callable] = {}
        self._is_initialized = False
        self._instance_data: Dict[str, Any] = {}
        self.sticky = sticky

    @abstractmethod
    async def _execute(self, *args, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass

    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with simple state tracking"""
        # Transition to ACTIVE
        await self.transition_to_active()
        
        try:
            if not self._is_initialized:
                await self.initialize()
            return await self._execute(*args, **kwargs)
        finally:
            # Always return to IDLE
            await self.transition_to_idle()

    async def initialize(self, instance_data: Optional[Dict[str, Any]] = None) -> None:
        """Initialize tool resources"""
        if instance_data:
            self._instance_data.update(instance_data)
        self._is_initialized = True

    def add_error_handler(self, error_type: type, handler: callable) -> None:
        """Add error handler for specific error types"""
        self._error_handlers[error_type] = handler

    def validate_permissions(self, granted_permissions: List[ToolPermission]) -> bool:
        """Validate that all required permissions are granted"""
        return all(
            perm in granted_permissions 
            for perm in self.config.required_permissions
        )

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
        """String representation"""
        return f"{self.name}: {self.description}"
