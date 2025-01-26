"""GLUE Tool Base System"""

import asyncio
from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from ..core.resource import Resource, ResourceState
from ..core.registry import ResourceRegistry
from ..core.types import BindingState


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
    - Optional magnetic capabilities
    """
    def __init__(
        self,
        name: str,
        description: str,
        config: Optional[ToolConfig] = None,
        permissions: Optional[Set[str]] = None,
        magnetic: bool = False,
        sticky: bool = False,
        shared_resources: Optional[List[str]] = None,
        binding_type: Optional['AdhesiveType'] = None
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
        self._instance_data: Dict[str, Any] = {}
        
        # Magnetic configuration (optional)
        self.magnetic = magnetic
        self.sticky = sticky
        self.shared_resources = shared_resources or []
        
        # Binding configuration (optional)
        if magnetic:
            from ..core.binding import AdhesiveType
            self.binding_type = binding_type or AdhesiveType.GLUE
            
            # Add magnetic permission if needed
            if ToolPermission.MAGNETIC not in self.config.required_permissions:
                self.config.required_permissions.append(ToolPermission.MAGNETIC)

    @abstractmethod
    async def _execute(self, *args, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass

    async def _validate_binding(self) -> None:
        """Validate binding state if tool is bound"""
        if not hasattr(self, '_binding'):
            return
            
        if self._binding.state == BindingState.FAILED:
            raise RuntimeError(f"Tool {self.name} binding has failed")
        if self._binding.should_break():
            raise RuntimeError(f"Tool {self.name} binding has expired")
        
        # Record tool usage in binding
        self._binding.use()

    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with simple state tracking"""
        # Transition to ACTIVE
        await self.transition_to_active()
        
        try:
            # Validate binding if magnetic
            if self.magnetic:
                await self._validate_binding()
            
            # Initialize if needed and execute
            if not self._is_initialized:
                await self.initialize()
            result = await self._execute(*args, **kwargs)
            
            # Store result in binding if magnetic
            if self.magnetic and hasattr(self, '_binding') and self._binding.maintains_context():
                self._binding.store_resource('last_result', result)
            
            return result
        except Exception as e:
            # Handle binding failure if magnetic
            if self.magnetic and hasattr(self, '_binding') and self._binding.state == BindingState.FAILED:
                raise RuntimeError(f"Tool {self.name} binding broke during use") from e
            raise
        finally:
            # Always return to IDLE
            await self.transition_to_idle()

    async def initialize(self, instance_data: Optional[Dict[str, Any]] = None) -> None:
        """Initialize tool resources"""
        if instance_data:
            self._instance_data.update(instance_data)
        self._is_initialized = True
        
    def create_instance(self, binding: Optional['ToolBinding'] = None) -> 'BaseTool':
        """Create a new instance of this tool with shared configuration"""
        instance = self.__class__(
            name=self.name,
            description=self.description,
            config=self.config,
            permissions=self.permissions,
            magnetic=self.magnetic,
            sticky=self.sticky,
            shared_resources=self.shared_resources,
            binding_type=self.binding_type
        )
        
        # Set binding if provided
        if binding:
            instance._binding = binding
            
        return instance
        
    def create_isolated_instance(self) -> 'BaseTool':
        """Create an isolated instance with no shared data"""
        instance = self.create_instance()
        instance._instance_data = {}  # Empty instance data
        return instance

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

    # Magnetic API methods (only used if magnetic=True)
    async def share_resource(self, name: str, value: Any) -> None:
        """Share resource with attracted resources"""
        if not self.magnetic or name not in self.shared_resources:
            return
            
        if self._attracted_to:
            for resource in self._attracted_to:
                if hasattr(resource, name):
                    setattr(resource, name, value)

    def get_shared_resource(self, name: str) -> Optional[Any]:
        """Get shared resource from attracted resources"""
        if not self.magnetic or name not in self.shared_resources:
            return None
            
        if self._attracted_to:
            for resource in self._attracted_to:
                if hasattr(resource, name):
                    return getattr(resource, name)
        return None

    def __str__(self) -> str:
        """String representation"""
        status = f"{self.name}: {self.description}"
        if self.magnetic:
            status += f" (Magnetic Tool"
            if self.binding_type:
                status += f" Binding: {self.binding_type.name}"
            if self.shared_resources:
                status += f" Shares: {', '.join(self.shared_resources)}"
            if self.sticky:
                status += " Sticky"
            status += f" State: {self.state.name})"
        return status

# ==================== Tool Registry ====================
class ToolRegistry(ResourceRegistry):
    """Registry specialized for tools"""
    def __init__(self):
        super().__init__()
        self._granted_permissions: Dict[str, List[ToolPermission]] = {}

    def register(self, tool: BaseTool, category: str = None) -> None:
        """Register a tool or resource"""
        if isinstance(tool, BaseTool):
            super().register(tool, "tool")
        else:
            if not category:
                raise ValueError("Category required for non-tool resources")
            super().register(tool, category)

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool"""
        self.register(tool)

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
        *args,
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

        return await tool.safe_execute(*args, **kwargs)

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
