# src/glue/tools/magnetic.py

import asyncio
from typing import List, Optional, Any, Dict, Type
from dataclasses import dataclass, field
from .base import BaseTool
from ..magnetic.field import MagneticResource, ResourceState
from ..core.registry import ResourceRegistry
from ..core.context import InteractionType
from ..core.types import AdhesiveType
from ..magnetic.rules import InteractionPattern

class ResourceLockedException(Exception):
    """Raised when trying to access a locked resource"""
    pass

class ResourceStateException(Exception):
    """Raised when a resource is in an invalid state for an operation"""
    pass

@dataclass
class ToolInstance:
    """Instance of a tool with its own state"""
    tool_class: Type['MagneticTool']
    binding_type: AdhesiveType
    shared_data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    state: ResourceState = ResourceState.IDLE

class MagneticTool(BaseTool, MagneticResource):
    """
    Base class for tools that can share resources in a magnetic workspace
    
    Features:
    - Instance management based on binding type
    - Resource persistence levels
    - Interaction pattern support
    - Workspace integration
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        registry: ResourceRegistry,
        magnetic: bool = True,
        shared_resources: Optional[List[str]] = None,
        sticky: bool = False,
        binding_type: AdhesiveType = AdhesiveType.VELCRO,
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
        
        # Tool-specific attributes
        self.binding_type = binding_type
        self._shared_data: Dict[str, Any] = {}
        self._workspace = None
        self._pending_tasks: List[asyncio.Task] = []
        self._state = ResourceState.IDLE
        self._instances: Dict[str, ToolInstance] = {}

    def create_instance(self, binding_type: Optional[AdhesiveType] = None) -> 'MagneticTool':
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
            registry=self._registry,
            magnetic=self.magnetic,
            shared_resources=self.shared_resources,
            sticky=self.sticky,
            binding_type=instance.binding_type
        )
        
        # Copy context if available
        if self._context:
            tool._context = self._context.copy()
        
        return tool

    def create_isolated_instance(self) -> 'MagneticTool':
        """Create an isolated instance (TAPE binding)"""
        return self.create_instance(AdhesiveType.TAPE)

    async def attach_to_workspace(self, workspace) -> None:
        """Attach tool to a magnetic workspace"""
        if self.magnetic:
            if not self._current_field:
                raise ResourceStateException("Tool must be in a field before attaching to workspace")
            
            self._workspace = workspace
            
            # Load persistent data based on binding type
            if hasattr(workspace, 'load_tool_data'):
                if self.binding_type == AdhesiveType.GLUE:
                    # Full persistence - load all data
                    self._shared_data = await workspace.load_tool_data(self.name)
                elif self.binding_type == AdhesiveType.VELCRO and self.sticky:
                    # Session persistence - load only sticky data
                    data = await workspace.load_tool_data(self.name)
                    self._shared_data = {k: v for k, v in data.items() if k in self.shared_resources}
            
            # Enter magnetic field
            if hasattr(workspace, 'field'):
                await self.enter_field(workspace.field)
            elif hasattr(workspace, '_resources'):
                await self.enter_field(workspace)

    async def detach_from_workspace(self) -> None:
        """Detach tool from its workspace"""
        if self._workspace and self.magnetic:
            # Save data based on binding type
            if hasattr(self._workspace, 'save_tool_data'):
                if self.binding_type == AdhesiveType.GLUE:
                    # Full persistence - save all data
                    await self._workspace.save_tool_data(self.name, self._shared_data)
                elif self.binding_type == AdhesiveType.VELCRO and self.sticky:
                    # Session persistence - save only sticky data
                    sticky_data = {k: v for k, v in self._shared_data.items() if k in self.shared_resources}
                    await self._workspace.save_tool_data(self.name, sticky_data)
            
            # Clear non-persistent data
            if self.binding_type == AdhesiveType.TAPE:
                self._shared_data.clear()
            
            # Exit field
            if self._current_field:
                await self.exit_field()
            
            self._workspace = None
            self._state = ResourceState.IDLE

    async def share_resource(
        self,
        resource_name: str,
        data: Any,
        pattern: InteractionPattern = InteractionPattern.ATTRACT
    ) -> None:
        """
        Share a resource with other tools
        
        Args:
            resource_name: Name of resource to share
            data: Resource data
            pattern: Interaction pattern to use
        """
        if not self.magnetic:
            raise ValueError("Tool must be magnetic to share resources")
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        
        # Store original states
        original_states = {}
        
        try:
            # Update state based on pattern
            if pattern == InteractionPattern.PUSH:
                self._state = ResourceState.SHARED
            elif pattern == InteractionPattern.PULL:
                self._state = ResourceState.PULLING
            else:
                self._state = ResourceState.SHARED
            
            self._shared_data[resource_name] = data
            
            # Share with attracted tools based on pattern
            if self._current_field:
                for tool in self._attracted_to:
                    if isinstance(tool, MagneticTool):
                        # Update tool state based on pattern
                        if pattern == InteractionPattern.PUSH:
                            tool._state = ResourceState.SHARED
                        elif pattern == InteractionPattern.PULL:
                            tool._state = ResourceState.SHARED
                        else:
                            tool._state = ResourceState.SHARED
                        
                        task = asyncio.create_task(
                            tool._on_resource_shared(self, resource_name, data, pattern)
                        )
                        self._pending_tasks.append(task)
                
                # Clean up completed tasks
                self._pending_tasks = [t for t in self._pending_tasks if not t.done()]
                
                # Wait for notifications
                if self._pending_tasks:
                    await asyncio.gather(*self._pending_tasks)
        
        except Exception as e:
            # Restore states on error
            for tool, state in original_states.items():
                tool._state = state
            raise e

    def get_shared_resource(
        self,
        resource_name: str,
        pattern: InteractionPattern = InteractionPattern.ATTRACT
    ) -> Any:
        """
        Get a shared resource
        
        Args:
            resource_name: Name of resource to get
            pattern: Interaction pattern to use
        """
        if not self.magnetic:
            raise ValueError("Tool must be magnetic to access shared resources")
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        
        # Check attracted tools based on pattern
        if self._current_field:
            for tool in self._attracted_to:
                if isinstance(tool, MagneticTool):
                    if pattern == InteractionPattern.PULL:
                        # Only get from SHARED tools when pulling
                        if tool._state == ResourceState.SHARED:
                            data = tool._get_shared_data(resource_name)
                            if data is not None:
                                return data
                    else:
                        data = tool._get_shared_data(resource_name)
                        if data is not None:
                            return data
        
        # Check workspace based on binding type
        if self._workspace and hasattr(self._workspace, 'get_tool_data'):
            if self.binding_type == AdhesiveType.GLUE:
                # Full persistence - check all workspace data
                workspace_data = self._workspace.get_tool_data(self.name)
                if workspace_data and resource_name in workspace_data:
                    return workspace_data[resource_name]
            elif self.binding_type == AdhesiveType.VELCRO and self.sticky:
                # Session persistence - check only sticky data
                workspace_data = self._workspace.get_tool_data(self.name)
                if workspace_data and resource_name in workspace_data:
                    if resource_name in self.shared_resources:
                        return workspace_data[resource_name]
        
        # Check local data
        return self._shared_data.get(resource_name)

    def _get_shared_data(self, resource_name: str) -> Optional[Any]:
        """Get shared data for a specific resource"""
        return self._shared_data.get(resource_name)

    async def _on_resource_shared(
        self,
        source: 'MagneticTool',
        resource_name: str,
        data: Any,
        pattern: InteractionPattern = InteractionPattern.ATTRACT
    ) -> None:
        """Handle shared resource notification"""
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
            
            # Reset state and cleanup
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
        """Clean up resources"""
        try:
            # Wait for pending tasks
            if self._pending_tasks:
                await asyncio.gather(*self._pending_tasks)
            
            # Clean up field connections
            if self._current_field:
                for other in list(self._attracted_to):
                    await self.break_attraction(other)
                for other in list(self._repelled_by):
                    await self.break_repulsion(other)
            
            # Reset state
            self._state = ResourceState.IDLE
            self._current_field = None
            self._context = None
            
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
        """
        Initialize tool with instance data
        
        Args:
            instance_data: Optional instance-specific data for tool initialization
        """
        # Load instance data if provided
        if instance_data:
            self._shared_data.update(instance_data)
        
        # Call parent initialize
        await super().initialize(instance_data)

    async def execute(self, *args, **kwargs) -> Any:
        """Execute with state validation"""
        # Validate field presence
        if self.magnetic and not self._current_field:
            raise ResourceStateException("Tool must be in a field before execution")
        
        # Check lock state
        if self._current_field and self._current_field.is_resource_locked(self):
            raise ResourceStateException("Resource is locked")
        
        # Store original state
        original_state = self._state
        
        try:
            # Update state based on context
            if kwargs.get("context"):
                context = kwargs["context"]
                if context.interaction_type == InteractionType.CHAT:
                    # Chat mode
                    self._state = ResourceState.CHATTING
                    if self._current_field and self._attracted_to:
                        for other in self._attracted_to:
                            other._state = ResourceState.CHATTING
                            await self._current_field.enable_chat(self, other)
                elif context.interaction_type == InteractionType.PULL:
                    # Pull mode
                    self._state = ResourceState.PULLING
                    if self._current_field and self._attracted_to:
                        for other in self._attracted_to:
                            other._state = ResourceState.SHARED
                            await self._current_field.enable_pull(self, other)
                elif context.interaction_type == InteractionType.PUSH:
                    # Push mode
                    self._state = ResourceState.SHARED
                    if self._current_field and self._attracted_to:
                        for other in self._attracted_to:
                            other._state = ResourceState.SHARED
                            await self._current_field.enable_push(self, other)
            elif self._attracted_to:
                # Shared mode
                self._state = ResourceState.SHARED
                if self._current_field:
                    for other in self._attracted_to:
                        other._state = ResourceState.SHARED
                        await self._current_field.attract(self, other)
            
            # Execute
            result = await super().execute(*args, **kwargs)
            
            # Restore state if not explicitly changed
            if self._state == ResourceState.SHARED and not self._attracted_to:
                self._state = original_state
            
            return result
            
        except Exception as e:
            # Restore state on error
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
            status += f" State: {self._state.name})"
        return status
