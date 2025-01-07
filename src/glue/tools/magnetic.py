# src/glue/tools/magnetic.py

import asyncio
from typing import List, Optional, Any, Dict
from .base import BaseTool
from ..magnetic.field import MagneticResource, ResourceState
from ..core.registry import ResourceRegistry
from ..core.context import InteractionType

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
        registry: ResourceRegistry,
        magnetic: bool = True,  # Magnetic tools are magnetic by default
        shared_resources: Optional[List[str]] = None,
        sticky: bool = False,
        **kwargs
    ):
        # Initialize base tool
        BaseTool.__init__(
            self,
            name=name,
            description=description,
            magnetic=magnetic,
            sticky=sticky,
            shared_resources=shared_resources,
            **kwargs
        )
        
        # Initialize magnetic resource attributes
        self.name = name
        self._context = None
        self._current_field = None
        self._attracted_to = set()
        self._repelled_by = set()
        self._event_handlers = {}
        
        self._shared_data: Dict[str, Any] = {}
        self._workspace = None
        self._pending_tasks: List[asyncio.Task] = []
        self._state = ResourceState.IDLE

    async def attach_to_workspace(self, workspace) -> None:
        """Attach tool to a magnetic workspace"""
        if self.magnetic:
            if not self._current_field:
                raise ResourceStateException("Tool must be in a field before attaching to workspace")
            
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
            self._state = ResourceState.IDLE

    async def share_resource(self, resource_name: str, data: Any) -> None:
        """Share a resource with other tools in the workspace"""
        if not self.magnetic:
            raise ValueError("Tool must be magnetic to share resources")
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        
        # Store original states
        original_states = {}
        
        try:
            # Update state to SHARED when sharing resources
            if self._state not in [ResourceState.CHATTING, ResourceState.PULLING]:
                original_states[self] = self._state
                self._state = ResourceState.SHARED
            
            self._shared_data[resource_name] = data
            
            # Notify attracted tools of new data
            if self._current_field:
                for tool in self._attracted_to:
                    if isinstance(tool, MagneticTool):
                        # Store original state
                        if tool._state not in [ResourceState.CHATTING, ResourceState.PULLING]:
                            original_states[tool] = tool._state
                            tool._state = ResourceState.SHARED
                        
                        task = asyncio.create_task(tool._on_resource_shared(self, resource_name, data))
                        self._pending_tasks.append(task)
                
                # Clean up completed tasks
                self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
                
                # Wait for all notifications to complete
                if self._pending_tasks:
                    await asyncio.gather(*self._pending_tasks)
        
        except Exception as e:
            # Restore original states on error
            for tool, state in original_states.items():
                tool._state = state
            raise e

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

    def on_event(self, event_type: str, handler: callable) -> None:
        """Register event handler"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _emit_event(self, event_type: str, data: Any) -> None:
        """Emit event to handlers"""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(self, data)
                    else:
                        handler(self, data)
                except Exception as e:
                    # Log error but don't break event chain
                    print(f"Error in event handler: {str(e)}")

    async def break_attraction(self, other: 'MagneticResource') -> None:
        """Break attraction with another resource"""
        self._attracted_to.discard(other)
        other._attracted_to.discard(self)
        
        # Update states if no more attractions
        if not self._attracted_to:
            self._state = ResourceState.IDLE
        if not other._attracted_to:
            other._state = ResourceState.IDLE
        
        await self._emit_event("attraction_break", other)
        await other._emit_event("attraction_break", self)
        
        # Notify registry
        if self._registry:
            self._registry._notify_observers("attraction_break", {
                "source": self.name,
                "target": other.name
            })

    async def break_repulsion(self, other: 'MagneticResource') -> None:
        """Break repulsion with another resource"""
        self._repelled_by.discard(other)
        other._repelled_by.discard(self)
        
        await self._emit_event("repulsion_break", other)
        await other._emit_event("repulsion_break", self)
        
        # Notify registry
        if self._registry:
            self._registry._notify_observers("repulsion_break", {
                "source": self.name,
                "target": other.name
            })

    def clear_resources(self) -> None:
        """Clear all shared resources"""
        self._shared_data.clear()
        if self._workspace and hasattr(self._workspace, 'clear_tool_data'):
            self._workspace.clear_tool_data(self.name)

    async def enter_field(self, field: 'MagneticField', registry: Optional['ResourceRegistry'] = None) -> None:
        """Enter a magnetic field"""
        self._current_field = field
        if registry:
            self._registry = registry
            
        await self._emit_event("field_enter", field)
        
        # Notify registry
        if self._registry:
            self._registry._notify_observers("field_enter", {
                "resource": self.name,
                "field": field.name
            })

    async def exit_field(self) -> None:
        """Exit current field"""
        if self._current_field:
            # Clean up attractions/repulsions
            for other in list(self._attracted_to):
                await self.break_attraction(other)
            for other in list(self._repelled_by):
                await self.break_repulsion(other)
            
            old_field = self._current_field
            self._current_field = None
            
            # Reset state and cleanup attributes
            self._state = ResourceState.IDLE
            self._context = None
            
            await self._emit_event("field_exit", old_field)
            
            # Notify registry
            if self._registry:
                self._registry._notify_observers("field_exit", {
                    "resource": self.name,
                    "field": old_field.name
                })
                self._registry = None

    async def cleanup(self) -> None:
        """Clean up resources when tool is done"""
        try:
            # Wait for any pending resource sharing tasks
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks)
            
            # Break all attractions and repulsions
            if self._current_field:
                for other in list(self._attracted_to):
                    await self.break_attraction(other)
                for other in list(self._repelled_by):
                    await self.break_repulsion(other)
            
            # Reset state and field
            self._state = ResourceState.IDLE
            self._current_field = None
            self._context = None
            
            # Clean up workspace
            await self.detach_from_workspace()
            
            # Clear shared data
            self._shared_data.clear()
            self._pending_tasks.clear()
            
            # Call parent cleanup
            await super().cleanup()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            raise

    async def execute(self, *args, **kwargs) -> Any:
        """Execute with state validation"""
        # Validate field presence for magnetic tools
        if self.magnetic and not self._current_field:
            raise ResourceStateException("Tool must be in a field before execution")
        
        # Check if resource is locked
        if self._current_field and self._current_field.is_resource_locked(self):
            raise ResourceStateException("Resource is locked")
        
        # Store original state
        original_state = self._state
        
        try:
            # Update state based on operation
            if kwargs.get("context"):
                context = kwargs["context"]
                if context.interaction_type == InteractionType.CHAT:
                    # Update states for chat mode
                    self._state = ResourceState.CHATTING
                    if self._current_field and self._attracted_to:
                        for other in self._attracted_to:
                            other._state = ResourceState.CHATTING
                            await self._current_field.enable_chat(self, other)
                elif context.interaction_type == InteractionType.PULL:
                    # Update states for pull mode
                    self._state = ResourceState.PULLING
                    if self._current_field and self._attracted_to:
                        for other in self._attracted_to:
                            other._state = ResourceState.SHARED
                            await self._current_field.enable_pull(self, other)
            elif self._attracted_to:
                # Update states for shared mode
                self._state = ResourceState.SHARED
                if self._current_field:
                    for other in self._attracted_to:
                        other._state = ResourceState.SHARED
                        await self._current_field.attract(self, other)
            
            # Execute operation
            result = await super().execute(*args, **kwargs)
            
            # Restore original state if not explicitly changed during execution
            if self._state == ResourceState.SHARED and not self._attracted_to:
                self._state = original_state
            
            return result
            
        except Exception as e:
            # Restore original state on error
            self._state = original_state
            raise e

    def __str__(self) -> str:
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
