"""GLUE Magnetic Field System"""

from typing import Any, Dict, List, Optional, Set, Type, Callable
from enum import Enum, auto
from contextlib import asynccontextmanager
import asyncio
from dataclasses import dataclass, field
from collections import defaultdict
from ..core.context import ContextState, InteractionType

# ==================== Enums ====================
class ResourceState(Enum):
    """States a resource can be in"""
    IDLE = auto()      # Not currently in use
    ACTIVE = auto()    # Currently in use
    LOCKED = auto()    # Cannot be used by others
    SHARED = auto()    # Being shared between resources
    CHATTING = auto()  # In direct model-to-model communication
    PULLING = auto()   # Receiving data only

# ==================== Event Types ====================
class FieldEvent:
    """Base class for field events"""
    pass

class ResourceAddedEvent(FieldEvent):
    """Event fired when a resource is added to the field"""
    def __init__(self, resource: 'MagneticResource'):
        self.resource = resource

class ResourceRemovedEvent(FieldEvent):
    """Event fired when a resource is removed from the field"""
    def __init__(self, resource: 'MagneticResource'):
        self.resource = resource

class AttractionEvent(FieldEvent):
    """Event fired when resources are attracted"""
    def __init__(self, source: 'MagneticResource', target: 'MagneticResource'):
        self.source = source
        self.target = target

class RepulsionEvent(FieldEvent):
    """Event fired when resources are repelled"""
    def __init__(self, source: 'MagneticResource', target: 'MagneticResource'):
        self.source = source
        self.target = target

class ContextChangeEvent(FieldEvent):
    """Event fired when context changes"""
    def __init__(self, context: ContextState):
        self.context = context

class ChatEvent(FieldEvent):
    """Event fired when models start chatting"""
    def __init__(self, model1: 'MagneticResource', model2: 'MagneticResource'):
        self.model1 = model1
        self.model2 = model2

class PullEvent(FieldEvent):
    """Event fired when a resource starts pulling from another"""
    def __init__(self, target: 'MagneticResource', source: 'MagneticResource'):
        self.target = target
        self.source = source

# ==================== Data Classes ====================
class MagneticResource:
    """Base class for resources that can be shared via magnetic fields"""
    def __init__(self, name: str):
        self.name = name
        self._current_field: Optional['MagneticField'] = None
        self._attracted_to: Set['MagneticResource'] = set()
        self._repelled_by: Set['MagneticResource'] = set()
        self._state: ResourceState = ResourceState.IDLE
        self._lock_holder: Optional['MagneticResource'] = None
        self._current_context: Optional[ContextState] = None
        self._required_for_context: bool = False

    def __hash__(self) -> int:
        """Make resource hashable based on name"""
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        """Compare resources based on name"""
        if not isinstance(other, MagneticResource):
            return NotImplemented
        return self.name == other.name

    def update_context(self, context: ContextState) -> None:
        """Update resource's context awareness"""
        self._current_context = context
        # Check if this resource is required for current context
        self._required_for_context = (
            hasattr(self, 'tool_name') and 
            self.tool_name in context.tools_required
        )

    def can_attract(self, other: 'MagneticResource') -> bool:
        """Check if attraction is allowed based on current context"""
        # If either resource is repelled, no attraction allowed
        if other in self._repelled_by or self in other._repelled_by:
            return False
        
        # If either resource is locked by someone else, no attraction allowed
        if (self._state == ResourceState.LOCKED and self._lock_holder != other or
            other._state == ResourceState.LOCKED and other._lock_holder != self):
            return False
        
        # In chat mode, only allow attraction if tools are required
        if self._current_context:
            if self._current_context.interaction_type == InteractionType.CHAT:
                return self._required_for_context or other._required_for_context
        
        return True

    async def attract_to(self, other: 'MagneticResource') -> bool:
        """Attempt to create attraction to another resource"""
        if not self.can_attract(other):
            return False
        
        self._attracted_to.add(other)
        other._attracted_to.add(self)
        
        await self.update_state()
        await other.update_state()
            
        return True

    async def repel_from(self, other: 'MagneticResource') -> None:
        """Create repulsion from another resource"""
        self._repelled_by.add(other)
        other._repelled_by.add(self)
        
        # Remove any existing attractions
        self._attracted_to.discard(other)
        other._attracted_to.discard(self)
        
        # Update states
        await self.update_state()
        await other.update_state()

    async def update_state(self) -> None:
        """Update the resource state based on its current attractions"""
        if not self._attracted_to:
            self._state = ResourceState.IDLE
        elif self._state != ResourceState.LOCKED:
            self._state = ResourceState.SHARED

    async def enter_field(self, field: 'MagneticField') -> None:
        """Enter a magnetic field"""
        if self._current_field and self._current_field != field:
            await self.exit_field()
        self._current_field = field
        self._state = ResourceState.IDLE

    async def exit_field(self) -> None:
        """Exit current magnetic field"""
        if self._current_field:
            for other in list(self._attracted_to):
                await self.repel_from(other)
            self._current_field = None
            self._attracted_to.clear()
            self._repelled_by.clear()
            self._state = ResourceState.IDLE
            self._lock_holder = None
            self._current_context = None
            self._required_for_context = False
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup method to be overridden by subclasses"""
        pass

    async def lock(self, holder: 'MagneticResource') -> bool:
        """Lock the resource for exclusive use"""
        if self._state == ResourceState.LOCKED:
            return False
        
        # Clear existing attractions except with holder
        for other in list(self._attracted_to):
            if other != holder:
                await self.repel_from(other)
        
        self._state = ResourceState.LOCKED
        self._lock_holder = holder
        return True

    async def unlock(self) -> None:
        """Unlock the resource"""
        self._state = ResourceState.IDLE
        self._lock_holder = None

    def __str__(self) -> str:
        status = f"{self.name} (State: {self._state.name}"
        if self._required_for_context:
            status += ", Required"
        status += ")"
        return status

    async def start_chat(self, other: 'MagneticResource') -> bool:
        """Start direct communication with another resource"""
        if not self.can_attract(other):
            return False
        
        self._state = ResourceState.CHATTING
        other._state = ResourceState.CHATTING
        self._attracted_to.add(other)
        other._attracted_to.add(self)
        return True

    async def start_pull(self, source: 'MagneticResource') -> bool:
        """Start pulling data from another resource"""
        if not self.can_attract(source):
            return False
        
        self._state = ResourceState.PULLING
        self._attracted_to.add(source)
        return True

# ==================== Main Classes ====================
class MagneticField:
    """
    Context manager for managing magnetic resources and their interactions.
    
    Example:
        ```python
        async with MagneticField("research") as field:
            await field.add_resource(tool1)
            await field.add_resource(tool2)
            await field.attract(tool1, tool2)
        ```
    """
    def __init__(
        self,
        name: str,
        parent: Optional['MagneticField'] = None
    ):
        self.name = name
        self.parent = parent
        self._resources: Dict[str, MagneticResource] = {}
        self._active = False
        self._event_handlers: Dict[Type[FieldEvent], List[Callable]] = defaultdict(list)
        self._child_fields: List['MagneticField'] = []
        self._current_context: Optional[ContextState] = None

    async def __aenter__(self) -> 'MagneticField':
        """Enter the magnetic field context"""
        self._active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the magnetic field context"""
        await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up the magnetic field"""
        # Clean up child fields first
        for child in self._child_fields:
            await child.cleanup()
        self._child_fields.clear()
        
        # Clean up resources
        for resource in list(self._resources.values()):
            await self.remove_resource(resource)
        
        self._active = False
        self._current_context = None

    async def update_context(self, context: ContextState) -> None:
        """Update field's context and propagate to resources"""
        self._current_context = context
        # Update all resources with new context
        for resource in self._resources.values():
            resource.update_context(context)
        # Emit context change event
        self._emit_event(ContextChangeEvent(context))

    async def add_resource(self, resource: MagneticResource) -> None:
        """Add a resource to the field"""
        if not self._active:
            raise RuntimeError("Cannot add resources to inactive field")
        
        if resource.name in self._resources:
            raise ValueError(f"Resource {resource.name} already exists in field")
        
        if resource._current_field:
            raise ValueError(f"Resource {resource.name} is already in another field")
        
        self._resources[resource.name] = resource
        # Ensure field membership is set
        await resource.enter_field(self)
        # Set current context if available
        if self._current_context:
            resource.update_context(self._current_context)
        self._emit_event(ResourceAddedEvent(resource))

    async def remove_resource(self, resource: MagneticResource) -> None:
        """Remove a resource from the field"""
        if resource.name in self._resources:
            del self._resources[resource.name]
            try:
                # Repel from all attracted resources
                for attracted in list(resource._attracted_to):
                    if attracted.name in self._resources:
                        await self.repel(resource, attracted)
                
                await resource.exit_field()
            except Exception as e:
                # Propagate the error but ensure the resource is removed
                self._emit_event(ResourceRemovedEvent(resource))
                raise e
            self._emit_event(ResourceRemovedEvent(resource))

    async def attract(
        self,
        source: MagneticResource,
        target: MagneticResource
    ) -> bool:
        """Create attraction between two resources"""
        if not (source.name in self._resources and target.name in self._resources):
            raise ValueError("Both resources must be in the field")
        
        success = await source.attract_to(target)
        if success:
            self._emit_event(AttractionEvent(source, target))
        return success

    async def repel(
        self,
        source: MagneticResource,
        target: MagneticResource
    ) -> None:
        """Create repulsion between two resources"""
        if not (source.name in self._resources and target.name in self._resources):
            return  # Silently ignore if either resource is not in the field
        
        await source.repel_from(target)
        self._emit_event(RepulsionEvent(source, target))

    def create_child_field(
        self,
        name: str
    ) -> 'MagneticField':
        """Create a child field that inherits from this field"""
        child = MagneticField(name, parent=self)
        child._active = True  # Activate child field immediately
        if self._current_context:  # Inherit parent's context
            child._current_context = self._current_context
        self._child_fields.append(child)
        return child

    def on_event(
        self,
        event_type: Type[FieldEvent],
        handler: Callable[[FieldEvent], None]
    ) -> None:
        """Register an event handler"""
        self._event_handlers[event_type].append(handler)

    def _emit_event(self, event: FieldEvent) -> None:
        """Emit an event to all registered handlers"""
        for handler in self._event_handlers[type(event)]:
            handler(event)
        # Propagate to parent field
        if self.parent:
            self.parent._emit_event(event)

    def get_resource(self, name: str) -> Optional[MagneticResource]:
        """Get a resource by name"""
        return self._resources.get(name)

    def list_resources(self) -> List[str]:
        """List all resources in the field"""
        return list(self._resources.keys())

    def get_attractions(
        self,
        resource: MagneticResource
    ) -> Set[MagneticResource]:
        """Get all resources attracted to the given resource"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._attracted_to.copy()

    def get_repulsions(
        self,
        resource: MagneticResource
    ) -> Set[MagneticResource]:
        """Get all resources repelled by the given resource"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._repelled_by.copy()

    def get_resource_state(
        self,
        resource: MagneticResource
    ) -> ResourceState:
        """Get the current state of a resource"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._state

    async def lock_resource(
        self,
        resource: MagneticResource,
        holder: MagneticResource
    ) -> bool:
        """Lock a resource for exclusive use"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return await resource.lock(holder)

    async def unlock_resource(
        self,
        resource: MagneticResource
    ) -> None:
        """Unlock a resource"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        await resource.unlock()

    def __str__(self) -> str:
        status = f"MagneticField({self.name}, resources={len(self._resources)}"
        if self._current_context:
            status += f", mode={self._current_context.interaction_type.name}"
        status += ")"
        return status

    async def enable_chat(self, model1: MagneticResource, model2: MagneticResource) -> bool:
        """Enable direct communication between models"""
        if not (model1.name in self._resources and model2.name in self._resources):
            raise ValueError("Both models must be in the field")
        
        success = await model1.start_chat(model2)
        if success:
            self._emit_event(ChatEvent(model1, model2))
        return success

    async def enable_pull(self, target: MagneticResource, source: MagneticResource) -> bool:
        """Enable one-way data flow"""
        if not (target.name in self._resources and source.name in self._resources):
            raise ValueError("Both resources must be in the field")
        
        success = await target.start_pull(source)
        if success:
            self._emit_event(PullEvent(target, source))
        return success
