# src/glue/tools/base.py

# ==================== Imports ====================
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

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
class BaseTool(ABC):
    """Base class for all tools"""
    def __init__(
        self,
        name: str,
        description: str,
        config: Optional[ToolConfig] = None
    ):
        self.name = name
        self.description = description
        self.config = config or ToolConfig(required_permissions=[])
        self._is_initialized = False
        self._error_handlers: Dict[type, callable] = {}

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool's main functionality"""
        pass

    async def initialize(self) -> None:
        """Initialize any required resources"""
        self._is_initialized = True

    async def cleanup(self) -> None:
        """Cleanup any resources"""
        self._is_initialized = False

    def add_error_handler(self, error_type: type, handler: callable) -> None:
        """Add an error handler for specific error types"""
        self._error_handlers[error_type] = handler

    def validate_permissions(self, granted_permissions: List[ToolPermission]) -> bool:
        """Validate that all required permissions are granted"""
        return all(
            perm in granted_permissions 
            for perm in self.config.required_permissions
        )

    async def safe_execute(self, **kwargs) -> Any:
        """Execute with error handling and validation"""
        if not self._is_initialized:
            await self.initialize()

        try:
            return await self.execute(**kwargs)
        except Exception as e:
            handler = self._error_handlers.get(type(e))
            if handler:
                return await handler(e)
            raise

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"

# ==================== Tool Registry ====================
class ToolRegistry:
    """Registry for managing available tools"""
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._granted_permissions: Dict[str, List[ToolPermission]] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool"""
        if tool_name in self._tools:
            del self._tools[tool_name]

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(tool_name)

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
        return list(self._tools.keys())

    def get_tool_description(self, tool_name: str) -> Optional[str]:
        """Get the description of a tool"""
        tool = self.get_tool(tool_name)
        return str(tool) if tool else None
