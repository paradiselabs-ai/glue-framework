# src/glue/tools/magnetic.py

import asyncio
from typing import List, Optional, Any, Dict
from .base import BaseTool
from ..magnetic.field import MagneticResource

class ResourceLockedException(Exception):
    """Raised when trying to access a locked resource"""
    pass

class ResourceStateException(Exception):
    """Raised when a resource is in an invalid state for an operation"""
    pass

class MagneticTool(BaseTool, MagneticResource):
    """Base class for tools that can share resources in a magnetic workspace"""
    
    def __init__(
        self,
        name: str,
        description: str,
        magnetic: bool = False,
        shared_resources: Optional[List[str]] = None,
        sticky: bool = False,
        **kwargs
    ):
        # Initialize both base classes
        BaseTool.__init__(self, name=name, description=description, **kwargs)
        MagneticResource.__init__(self, name=name)
        
        self.magnetic = magnetic
        self.shared_resources = shared_resources or []
        self.sticky = sticky
        self._shared_data: Dict[str, Any] = {}
        self._workspace = None
        self._pending_tasks: List[asyncio.Task] = []

    async def attach_to_workspace(self, workspace) -> None:
        """Attach tool to a magnetic workspace"""
        if self.magnetic:
            self._workspace = workspace
            # Load any sticky resources from workspace if it supports it
            if self.sticky and hasattr(workspace, 'load_tool_data'):
                self._shared_data = await workspace.load_tool_data(self.name)
            
            # Enter the magnetic field if workspace has one
            if hasattr(workspace, 'field'):
                await self.enter_field(workspace.field)
            # If workspace is a field, enter it directly
            elif hasattr(workspace, '_resources'):
                await self.enter_field(workspace)

    async def detach_from_workspace(self) -> None:
        """Detach tool from its workspace"""
        if self._workspace and self.magnetic:
            # Save sticky resources to workspace if it supports it
            if self.sticky and hasattr(self._workspace, 'save_tool_data'):
                await self._workspace.save_tool_data(self.name, self._shared_data)
            else:
                # Clear non-sticky resources
                self._shared_data.clear()
            
            # Exit the magnetic field if in one
            if self._current_field:
                await self.exit_field()
            
            self._workspace = None

    async def share_resource(self, resource_name: str, data: Any) -> None:
        """Share a resource with other tools in the workspace"""
        if not self.magnetic:
            raise ValueError("Tool must be magnetic to share resources")
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        self._shared_data[resource_name] = data
        
        # Notify attracted tools of new data
        if self._current_field:
            for tool in self._attracted_to:
                if isinstance(tool, MagneticTool):
                    task = asyncio.create_task(tool._on_resource_shared(self, resource_name, data))
                    self._pending_tasks.append(task)
                    # Clean up completed tasks
                    self._pending_tasks = [t for t in self._pending_tasks if not t.done()]

    def get_shared_resource(self, resource_name: str) -> Any:
        """Get a shared resource from the workspace"""
        if not self.magnetic:
            raise ValueError("Tool must be magnetic to access shared resources")
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        
        # First check attracted tools for the resource
        if self._current_field:
            for tool in self._attracted_to:
                if isinstance(tool, MagneticTool):
                    data = tool._get_shared_data(resource_name)
                    if data is not None:
                        return data
        
        # Then check workspace if it supports tool data
        if self._workspace and hasattr(self._workspace, 'get_tool_data'):
            workspace_data = self._workspace.get_tool_data(self.name)
            if workspace_data and resource_name in workspace_data:
                return workspace_data[resource_name]
        
        # Finally check local data
        return self._shared_data.get(resource_name)

    def _get_shared_data(self, resource_name: str) -> Optional[Any]:
        """Get shared data for a specific resource (called by other tools)"""
        return self._shared_data.get(resource_name)

    async def _on_resource_shared(self, source: 'MagneticTool', resource_name: str, data: Any) -> None:
        """Handle notification of shared resource from another tool"""
        # Override in subclasses to react to shared resources
        pass

    def clear_resources(self) -> None:
        """Clear all shared resources"""
        self._shared_data.clear()
        if self._workspace and hasattr(self._workspace, 'clear_tool_data'):
            self._workspace.clear_tool_data(self.name)

    async def cleanup(self) -> None:
        """Clean up resources when tool is done"""
        # Wait for any pending resource sharing tasks
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks)
        await self.detach_from_workspace()
        await super().cleanup()

    def __str__(self) -> str:
        status = []
        if self.magnetic:
            status.append("Magnetic")
            if self.shared_resources:
                status.append(f"Shares: {', '.join(self.shared_resources)}")
            if self.sticky:
                status.append("Sticky")
            if self._attracted_to:
                status.append(f"Attracted to: {len(self._attracted_to)} tools")
        return (
            f"{self.name}: {self.description} "
            f"({'Not ' if not self.magnetic else ''}Magnetic"
            f"{' - ' + ', '.join(status[1:]) if len(status) > 1 else ''})"
        )
