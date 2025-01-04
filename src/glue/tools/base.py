"""GLUE Tool Base System"""

from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from ..core.resource import Resource, ResourceState
from ..core.registry import ResourceRegistry

# ==================== Enums ====================
class ToolPermission(Enum):
    """Permissions that can be granted to tools"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    SYSTEM = "system"
    MAGNETIC = "magnetic"  # Permission for magnetic operations

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
class BaseTool(Resource, ABC):
    """
    Base class for all GLUE tools.
    
    Features:
    - Resource lifecycle management
    - Permission system
    - Error handling
    - Safe execution
    - State tracking
    - Field awareness
    - Magnetic capabilities
    """
    def __init__(
        self,
        name: str,
        description: str,
        config: Optional[ToolConfig] = None,
        permissions: Optional[Set[str]] = None,
        magnetic: bool = False,  # Keep magnetic flag for API compatibility
        sticky: bool = False,    # Keep sticky flag for API compatibility
        shared_resources: Optional[List[str]] = None  # Resources to share magnetically
    ):
        # Initialize base resource
        tags = {"tool", name}
        if magnetic:
            tags.add("magnetic")
            if sticky:
                tags.add("sticky")
        
        super().__init__(name, category="tool", tags=tags)
        
        # Tool-specific attributes
        self.description = description
        self.config = config or ToolConfig(required_permissions=[])
        self.permissions = permissions or set()
        self._error_handlers: Dict[type, callable] = {}
        self._is_initialized = False
        
        # Magnetic configuration
        self.magnetic = magnetic
        self.sticky = sticky
        self.shared_resources = shared_resources or []
        
        # Magnetic properties
        self._break_after_use = False
        self._allow_reconnect = False
        self._persist_context = False
        self._attract_mode = "none"
        
        # Add magnetic permission if needed
        if magnetic and ToolPermission.MAGNETIC not in self.config.required_permissions:
            self.config.required_permissions.append(ToolPermission.MAGNETIC)

    @abstractmethod
    async def _execute(self, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass

    async def execute(self, **kwargs) -> Any:
        """Execute tool with resource state tracking"""
        if self.state != ResourceState.IDLE:
            raise RuntimeError(f"Tool {self.name} is busy (state: {self.state.name})")
            
        self._state = ResourceState.ACTIVE
        try:
            if not self._is_initialized:
                await self.initialize()
            result = await self._execute(**kwargs)
            return result
        finally:
            self._state = ResourceState.IDLE

    async def initialize(self) -> None:
        """Initialize tool resources"""
        self._is_initialized = True

    async def cleanup(self) -> None:
        """Cleanup tool resources"""
        self._is_initialized = False
        await super().exit_field()

    def add_error_handler(self, error_type: type, handler: callable) -> None:
        """Add error handler for specific error types"""
        self._error_handlers[error_type] = handler

    def validate_permissions(self, granted_permissions: List[ToolPermission]) -> bool:
        """Validate that all required permissions are granted"""
        return all(
            perm in granted_permissions 
            for perm in self.config.required_permissions
        )

    async def safe_execute(self, **kwargs) -> Any:
        """Execute with error handling and validation"""
        try:
            return await self.execute(**kwargs)
        except Exception as e:
            handler = self._error_handlers.get(type(e))
            if handler:
                return await handler(e)
            raise

    # Magnetic API compatibility methods
    async def share_resource(self, name: str, value: Any) -> None:
        """Share resource with attracted resources (magnetic API compatibility)"""
        if not self.magnetic or name not in self.shared_resources:
            return
            
        if self._attracted_to:
            for resource in self._attracted_to:
                if hasattr(resource, name):
                    setattr(resource, name, value)

    def get_shared_resource(self, name: str) -> Optional[Any]:
        """Get shared resource from attracted resources (magnetic API compatibility)"""
        if not self.magnetic or name not in self.shared_resources:
            return None
            
        if self._attracted_to:
            for resource in self._attracted_to:
                if hasattr(resource, name):
                    return getattr(resource, name)
        return None

    def __str__(self) -> str:
        """String representation"""
        status = super().__str__()
        if self.magnetic:
            status += f" | Magnetic"
            if self.shared_resources:
                status += f" | Shares: {', '.join(self.shared_resources)}"
            if self.sticky:
                status += " | Sticky"
        return f"{status} | {self.description}"

# ==================== Tool Registry ====================
class ToolRegistry(ResourceRegistry):
    """
    Registry specialized for tools.
    
    Features:
    - Tool registration and lookup
    - Permission management
    - Safe execution
    - Resource tracking
    """
    def __init__(self):
        super().__init__()
        self._granted_permissions: Dict[str, List[ToolPermission]] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool"""
        self.register(tool, "tool")

    def unregister_tool(self, tool_name: str) -> None:
        """Unregister a tool"""
        self.unregister(tool_name)

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.get_resource(tool_name, "tool")

    def grant_permissions(
        self,
        tool_name: str,
        permissions: List[ToolPermission]
    ) -> None:
        """Grant permissions to a tool"""
        self._granted_permissions[tool_name] = permissions

    async def execute_tool(
        self,
        tool_name: str,
        **kwargs
    ) -> Any:
        """Execute a tool with permission checking"""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        granted = self._granted_permissions.get(tool_name, [])
        if not tool.validate_permissions(granted):
            raise PermissionError(
                f"Tool {tool_name} lacks required permissions"
            )

        return await tool.safe_execute(**kwargs)

    def list_tools(self) -> List[str]:
        """List all registered tools"""
        tools = self.get_resources_by_category("tool")
        return [t.name for t in tools]

    def get_tool_description(self, tool_name: str) -> Optional[str]:
        """Get the description of a tool"""
        tool = self.get_tool(tool_name)
        return str(tool) if tool else None

    def get_tool_permissions(self, tool_name: str) -> List[ToolPermission]:
        """Get granted permissions for a tool"""
        return self._granted_permissions.get(tool_name, [])
