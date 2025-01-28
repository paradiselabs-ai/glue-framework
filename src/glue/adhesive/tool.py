"""GLUE Adhesive Tool System

Provides tools with binding-based result persistence:

- TAPE: Temporary, single-use results
- VELCRO: Session-level result persistence
- GLUE: Team-level result persistence

Example Usage:
```python
# Temporary binding
tool = AdhesiveTool(binding_type=AdhesiveType.TAPE)
result = await tool.execute()  # Result discarded after use

# Session binding
tool = AdhesiveTool(binding_type=AdhesiveType.VELCRO)
result1 = await tool.execute()  # Result stored in session
result2 = await tool.get_last_result()  # Access previous result

# Team binding
tool = AdhesiveTool(binding_type=AdhesiveType.GLUE)
await tool.execute()  # Result stored at team level
```
"""

import asyncio
from typing import List, Optional, Any, Dict, Type
from dataclasses import dataclass, field
from ..core.types import AdhesiveType, ResourceState
from ..core.context import InteractionType
from ..core.tool_binding import ToolBinding
from ..tools.base import BaseTool

@dataclass
class ToolInstance:
    """Instance of a tool with its own binding"""
    tool_class: Type['AdhesiveTool']
    binding_type: AdhesiveType
    shared_data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    state: ResourceState = ResourceState.IDLE

class AdhesiveTool(BaseTool):
    """
    Base class for tools with binding-based result persistence.
    
    Features:
    - Instance management based on binding type
    - Result persistence through bindings
    - Workspace integration for result storage
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        shared_resources: Optional[List[str]] = None,
        binding_type: AdhesiveType = AdhesiveType.VELCRO,
        **kwargs
    ):
        # Initialize base tool
        super().__init__(
            name=name,
            description=description,
            binding_type=binding_type,
            **kwargs
        )
        
        # Tool-specific attributes
        self.shared_resources = shared_resources or []  # Resources this tool can share
        self._shared_data: Dict[str, Any] = {}
        self._workspace = None
        self._pending_tasks: List[asyncio.Task] = []
        self._instances: Dict[str, ToolInstance] = {}

    def create_instance(self, binding_type: Optional[AdhesiveType] = None) -> 'AdhesiveTool':
        """Create a new instance with specified binding"""
        instance_id = f"{self.name}_{len(self._instances)}"
        instance = ToolInstance(
            tool_class=self.__class__,
            binding_type=binding_type or self.binding_type
        )
        self._instances[instance_id] = instance
        
        # Create new tool instance
        tool = self.__class__(
            name=instance_id,
            description=self.description,
            binding_type=instance.binding_type
        )
        
        return tool

    def create_isolated_instance(self) -> 'AdhesiveTool':
        """Create an isolated instance (TAPE binding)"""
        return self.create_instance(AdhesiveType.TAPE)

    async def attach_to_workspace(self, workspace) -> None:
        """Attach tool to a workspace for result storage"""
        self._workspace = workspace
        
        # Load persistent data based on binding type
        if hasattr(workspace, 'load_tool_data'):
            if self._binding and self._binding.type == AdhesiveType.GLUE:
                # Full persistence - load all data
                self._shared_data = await workspace.load_tool_data(self.name)
            elif self._binding and self._binding.type == AdhesiveType.VELCRO:
                # Check workspace sticky status
                is_sticky = hasattr(workspace, 'sticky') and workspace.sticky
                if is_sticky:
                    # Load data for sticky workspaces
                    data = await workspace.load_tool_data(self.name)
                    self._shared_data = {k: v for k, v in data.items() if k in self._binding.shared_resources}

    async def detach_from_workspace(self) -> None:
        """Detach tool from its workspace"""
        if self._workspace:
            # Save data based on binding type and workspace sticky status
            if hasattr(self._workspace, 'save_tool_data'):
                if self._binding and self._binding.type == AdhesiveType.GLUE:
                    # Full persistence - save all data
                    await self._workspace.save_tool_data(self.name, self._shared_data)
                elif self._binding and self._binding.type == AdhesiveType.VELCRO:
                    # Check workspace sticky status
                    is_sticky = hasattr(self._workspace, 'sticky') and self._workspace.sticky
                    if is_sticky:
                        # Save data for sticky workspaces
                        sticky_data = {k: v for k, v in self._shared_data.items()
                                     if k in self._binding.shared_resources}
                        await self._workspace.save_tool_data(self.name, sticky_data)
            
            # Clear non-persistent data
            if self._binding and self._binding.type == AdhesiveType.TAPE:
                self._shared_data.clear()
            
            self._workspace = None

    async def cleanup(self) -> None:
        """Clean up resources"""
        try:
            # Wait for pending tasks
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks)
            
            # Clean up workspace
            await self.detach_from_workspace()
            
            # Clear data
            self._shared_data.clear()
            self._pending_tasks.clear()
            self._instances.clear()
            
            # Parent cleanup
            await super().cleanup()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            raise

    async def initialize(self, instance_data: Optional[Dict[str, Any]] = None) -> None:
        """Initialize tool with instance data"""
        # Load instance data if provided
        if instance_data:
            self._shared_data.update(instance_data)
        
        # Call parent initialize
        await super().initialize(instance_data)

    async def execute(self, *args, **kwargs) -> Any:
        """Execute with proper binding validation"""
        try:
            # Execute with binding validation
            result = await super().execute(*args, **kwargs)
            
            # Store result based on binding type
            if self._binding and self._binding.maintains_context():
                if self._binding.type == AdhesiveType.GLUE:
                    # Store at team level through workspace
                    if self._workspace and hasattr(self._workspace, 'store_tool_result'):
                        await self._workspace.store_tool_result(self.name, result)
                else:
                    # Store in binding's resource pool
                    self._binding.store_resource('last_result', result)
            
            return result
            
        except Exception as e:
            raise e

    def get_last_result(self) -> Optional[Any]:
        """Get last stored result based on binding type"""
        if not self._binding:
            return None
            
        if self._binding.type == AdhesiveType.GLUE:
            # Get from team level through workspace
            if self._workspace and hasattr(self._workspace, 'get_tool_result'):
                return self._workspace.get_tool_result(self.name)
        else:
            # Get from binding's resource pool
            return self._binding.get_resource('last_result')
        
        return None

    def __str__(self) -> str:
        """String representation showing binding type and workspace status"""
        status = f"{self.name}: {self.description}"
        if self._binding:
            status += f" (Binding: {self._binding.type.name}"
            if self._workspace and hasattr(self._workspace, 'sticky') and self._workspace.sticky:
                status += " [Workspace: Sticky]"
            status += ")"
        return status