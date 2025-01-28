"""GLUE Tool Base System"""

import asyncio
from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from ..core.state import StateManager
from ..core.tool_binding import ToolBinding
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


# ==================== Tool Configuration ====================
@dataclass
class ToolConfig:
    """Configuration for a tool"""
    required_permissions: List[ToolPermission]
    max_retries: int = 3
    timeout: float = 30.0
    cache_results: bool = False
    async_enabled: bool = True


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
    - State management through StateManager
    - Permission system
    - Error handling
    - Safe execution
    - Tool binding management
    - Result sharing through Team
    """
    def __init__(
        self,
        name: str,
        description: str,
        config: Optional[ToolConfig] = None,
        permissions: Optional[Set[str]] = None,
        binding_type: Optional['AdhesiveType'] = None
    ):
        # Initialize core components
        self.name = name
        self.description = description
        self._state_manager = StateManager()
        self._binding = ToolBinding(binding_type) if binding_type else None
        
        # Tool configuration
        self.config = config or ToolConfig(required_permissions=[])
        self.permissions = permissions or set()
        self._error_handlers: Dict[type, callable] = {}
        self._is_initialized = False
        self._instance_data: Dict[str, Any] = {}
        
        # Initialize state
        self._state_manager.initialize(self.name, ToolState.IDLE)

    @abstractmethod
    async def _execute(self, *args, **kwargs) -> Any:
        """Tool-specific implementation"""
        pass

    async def _validate_binding(self) -> None:
        """Validate binding state if tool is bound"""
        if not self._binding:
            return
            
        if self._binding.state == BindingState.FAILED:
            raise RuntimeError(f"Tool {self.name} binding has failed")
        if self._binding.should_break():
            raise RuntimeError(f"Tool {self.name} binding has expired")
        
        # Record tool usage in binding
        self._binding.use()

    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with state tracking and binding validation"""
        try:
            # Set state to ACTIVE
            await self._state_manager.transition_to(self.name, ToolState.ACTIVE)
            
            # Validate binding if present
            if self._binding:
                await self._validate_binding()
            
            # Initialize if needed
            if not self._is_initialized:
                await self.initialize()
                
            # Execute tool
            result = await self._execute(*args, **kwargs)
            
            # Store result based on binding type:
            # - TAPE: No storage (temporary)
            # - VELCRO: Stored in binding's session pool
            # - GLUE: Handled by Team.share_result()
            if self._binding and self._binding.maintains_context():
                self._binding.store_resource('last_result', result)
            
            return result
            
        except Exception as e:
            # Handle binding failures
            if self._binding and self._binding.state == BindingState.FAILED:
                raise RuntimeError(f"Tool {self.name} binding broke during use") from e
            raise
            
        finally:
            # Always return to IDLE
            await self._state_manager.transition_to(self.name, ToolState.IDLE)

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
            binding_type=binding.type if binding else None
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
        if self._binding:
            await self._binding.unbind()
        await self._state_manager.transition_to(self.name, ToolState.IDLE)

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
        status = f"{self.name}: {self.description}"
        if self._binding:
            status += f" (Binding: {self._binding.type.name})"
        return status


# ==================== Tool Registry ====================
class ToolRegistry:
    """Registry for managing tools and their permissions"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._granted_permissions: Dict[str, List[ToolPermission]] = {}
        
    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        
    def unregister(self, tool_name: str) -> None:
        """Unregister a tool"""
        if tool_name in self._tools:
            del self._tools[tool_name]
            if tool_name in self._granted_permissions:
                del self._granted_permissions[tool_name]
                
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(tool_name)
        
    def grant_permissions(
        self,
        tool_name: str,
        permissions: List[ToolPermission]
    ) -> None:
        """Grant permissions to a tool"""
        if tool_name not in self._tools:
            raise ValueError(f"Tool not found: {tool_name}")
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
        return list(self._tools.keys())
        
    def get_tool_description(self, tool_name: str) -> Optional[str]:
        """Get the description of a tool"""
        tool = self.get_tool(tool_name)
        return str(tool) if tool else None
        
    def get_tool_permissions(self, tool_name: str) -> List[ToolPermission]:
        """Get granted permissions for a tool"""
        return self._granted_permissions.get(tool_name, [])
