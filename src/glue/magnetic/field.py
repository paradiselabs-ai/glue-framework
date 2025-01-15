"""GLUE Magnetic Field System"""

import asyncio
from typing import Dict, List, Optional, Set, Type, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass
from collections import defaultdict
from ..core.state import StateManager
from ..core.types import ResourceState, MagneticResource, AdhesiveType
from .rules import RuleSet, AttractionRule, PolicyPriority, AttractionPolicy

if TYPE_CHECKING:
    from ..core.context import ContextState, InteractionType
    from ..core.registry import ResourceRegistry

# ==================== Event Types ====================
class FieldEvent:
    """Base class for field events"""
    pass

class ResourceAddedEvent(FieldEvent):
    """Event fired when a resource is added to the field"""
    def __init__(self, resource: MagneticResource):
        self.resource = resource

class ResourceRemovedEvent(FieldEvent):
    """Event fired when a resource is removed from the field"""
    def __init__(self, resource: MagneticResource):
        self.resource = resource

class AttractionEvent(FieldEvent):
    """Event fired when resources are attracted"""
    def __init__(self, source: MagneticResource, target: MagneticResource):
        self.source = source
        self.target = target

class RepulsionEvent(FieldEvent):
    """Event fired when resources are repelled"""
    def __init__(self, source: MagneticResource, target: MagneticResource):
        self.source = source
        self.target = target

class ContextChangeEvent(FieldEvent):
    """Event fired when context changes"""
    def __init__(self, context: 'ContextState'):
        self.context = context

class ChatEvent(FieldEvent):
    """Event fired when models start chatting"""
    def __init__(self, model1: MagneticResource, model2: MagneticResource):
        self.model1 = model1
        self.model2 = model2

class PullEvent(FieldEvent):
    """Event fired when a resource starts pulling from another"""
    def __init__(self, target: MagneticResource, source: MagneticResource):
        self.target = target
        self.source = source

# ==================== Main Class ====================
class MagneticField:
    """
    Context manager for managing resources and their interactions.
    
    Features:
    - Resource tracking via registry
    - Field-wide rules
    - Context propagation
    - Event handling
    - Hierarchical fields
    
    Example:
        ```python
        registry = ResourceRegistry()
        async with MagneticField("research", registry) as field:
            await field.add_resource(tool1)
            await field.add_resource(tool2)
            await field.attract(tool1, tool2)
        ```
    """
    def __init__(
        self,
        name: str,
        registry: 'ResourceRegistry',
        parent: Optional['MagneticField'] = None,
        rules: Optional[RuleSet] = None
    ):  
        self.name = name
        self.registry = registry
        self.parent = parent
        self._active = False
        self._event_handlers = defaultdict(list)
        self._child_fields = []
        self._current_context = None
        self._resources = {}
        self._state_manager = StateManager()  # Add state manager

        # Configure valid transitions
        self._setup_transitions()

        # Field-wide rules
        self._rules = rules or RuleSet(f"{name}_field_rules")
        self._rules.add_rule(AttractionRule(
            name="field_state",
            policy=AttractionPolicy.STATE_BASED,
            priority=PolicyPriority.SYSTEM,
            state_validator=lambda s1, s2: True,  # Remove old validation
            description="Field-wide state validation"
        ))

    def _setup_transitions(self):
        """Configure valid state transitions"""
        # IDLE transitions
        self._state_manager.add_transition(
            ResourceState.IDLE,
            ResourceState.SHARED,
            cleanup=self._cleanup_idle
        )
        self._state_manager.add_transition(
            ResourceState.IDLE,
            ResourceState.ACTIVE
        )

        # SHARED transitions
        self._state_manager.add_transition(
            ResourceState.SHARED,
            ResourceState.IDLE,
            cleanup=self._cleanup_shared
        )
        self._state_manager.add_transition(
            ResourceState.SHARED,
            ResourceState.CHATTING
        )
        self._state_manager.add_transition(
            ResourceState.SHARED,
            ResourceState.PULLING
        )

        # CHATTING transitions
        self._state_manager.add_transition(
            ResourceState.CHATTING,
            ResourceState.IDLE,
            cleanup=self._cleanup_chatting
        )

        # PULLING transitions
        self._state_manager.add_transition(
            ResourceState.PULLING,
            ResourceState.IDLE,
            cleanup=self._cleanup_pulling
        )

    async def _cleanup_idle(self, resource: 'Resource') -> None:
        """Cleanup when leaving IDLE state"""
        pass  # No cleanup needed from IDLE

    async def _cleanup_shared(self, resource: 'Resource') -> None:
        """Cleanup when leaving SHARED state"""
        # Break attractions if moving to IDLE
        if resource._next_state == ResourceState.IDLE:
            for other in list(resource._attracted_to):
                await self.break_attraction(resource, other)

    async def _cleanup_chatting(self, resource: 'Resource') -> None:
        """Cleanup when leaving CHATTING state"""
        # Break chat connections
        for other in list(resource._attracted_to):
            if other._state == ResourceState.CHATTING:
                await self.break_attraction(resource, other)

    async def _cleanup_pulling(self, resource: 'Resource') -> None:
        """Cleanup when leaving PULLING state"""
        # Break pull connections
        for other in list(resource._attracted_to):
            if other._state == ResourceState.SHARED:
                await self.break_attraction(resource, other)

    def is_active(self) -> bool:
        """Check if the magnetic field is currently active"""
        return self._active

    async def __aenter__(self) -> 'MagneticField':
        """Enter the magnetic field context"""
        self._active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the magnetic field context"""
        # Only cleanup if there was an error
        if exc_type is not None:
            await self.cleanup()
        # Only deactivate if we're the outermost context
        if not any(child._active for child in self._child_fields):
            self._active = False

    async def cleanup(self) -> None:
        """Clean up the magnetic field"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during cleanup
            if not self._active:
                self._active = True
            
            # Clean up child fields first
            for child in self._child_fields:
                await child.cleanup()
            self._child_fields.clear()
            
            # Clean up resources while field is still active
            resources = self.registry.get_resources_by_category("field:" + self.name)
            for resource in resources:
                await resource.exit_field()
                self.registry.unregister(resource.name)
            
            # Clear context
            self._current_context = None
            
            # Clear resources
            self._resources.clear()
        finally:
            # Restore original activation state
            self._active = was_active
            # Ensure field is deactivated after cleanup
            if was_active:
                self._active = False

    async def update_context(self, context: 'ContextState') -> None:
        """Update field's context and propagate to resources"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during context update
            if not self._active:
                self._active = True
            
            self._current_context = context
            
            # Update field rules if context provides any
            if hasattr(context, "rules"):
                self._rules = context.rules
            
            # Update all resources in field
            resources = self.registry.get_resources_by_category("field:" + self.name)
            for resource in resources:
                await resource.update_context(context)
            
            # Emit event
            self._emit_event(ContextChangeEvent(context))
        finally:
            # Restore original activation state
            self._active = was_active

    async def add_resource(self, resource: MagneticResource) -> None:
        """Add a resource to the field"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during resource addition
            if not self._active:
                self._active = True
            
            # Check if resource is already in field
            if self.registry.get_resource(resource.name, "field:" + self.name):
                await resource.exit_field()
                self.registry.unregister(resource.name)
            
            # Register resource first
            self.registry.register(resource, "field:" + self.name)
            
            # Then enter field
            await resource.enter_field(self, self.registry)
            
            # Add to internal resources dict
            self._resources[resource.name] = resource
            
            # Set current context if available
            if self._current_context:
                await resource.update_context(self._current_context)
            
            # Emit event
            self._emit_event(ResourceAddedEvent(resource))
        finally:
            # Restore original activation state
            self._active = was_active

    async def remove_resource(self, resource: MagneticResource) -> None:
        """Remove a resource from the field"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during resource removal
            if not self._active:
                self._active = True
            
            if self.registry.get_resource(resource.name, "field:" + self.name):
                await resource.exit_field()
                self.registry.unregister(resource.name)
                # Remove from internal resources dict
                if resource.name in self._resources:
                    del self._resources[resource.name]
                self._emit_event(ResourceRemovedEvent(resource))
        finally:
            # Restore original activation state
            self._active = was_active

    async def attract(
        self,
        source: MagneticResource,
        target: MagneticResource
    ) -> bool:
        """Create attraction between two resources"""
        # Save current activation state
        was_active = self._active

        try:
            # Ensure field is active during attraction
            if not self._active:
                self._active = True

            # Verify resources are in field
            if not (
                self.registry.get_resource(source.name, f"field:{self.name}") and
                self.registry.get_resource(target.name, f"field:{self.name}")
            ):
                raise ValueError("Both resources must be in the field")

            # Check field rules
            if not self._rules.validate(source, target):
                return False

            # Transition states
            try:
                await self._state_manager.transition(source, ResourceState.SHARED, self._current_context)
                await self._state_manager.transition(target, ResourceState.SHARED, self._current_context)
            except:
                return False

            # Create attraction
            success = await source.attract_to(target)
            if success:
                # Emit event
                self._emit_event(AttractionEvent(source, target))
            return success
        finally:
            # Restore original activation state
            self._active = was_active

    async def repel(
        self,
        source: MagneticResource,
        target: MagneticResource
    ) -> None:
        """Create repulsion between two resources"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during repulsion
            if not self._active:
                self._active = True
            
            # Verify resources are in field
            if not (
                self.registry.get_resource(source.name, "field:" + self.name) and
                self.registry.get_resource(target.name, "field:" + self.name)
            ):
                raise ValueError("Both resources must be in the field")
            
            # Create repulsion
            await source.repel_from(target)
            self._emit_event(RepulsionEvent(source, target))
        finally:
            # Restore original activation state
            self._active = was_active

    def create_child_field(
        self,
        name: str
    ) -> 'MagneticField':
        """Create a child field that inherits from this field"""
        child = MagneticField(
            name=name,
            registry=self.registry,
            parent=self,
            rules=self._rules.copy()  # Inherit parent rules
        )
        child._active = True
        if self._current_context:
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

    def is_resource_shared(self, resource: MagneticResource) -> bool:
        """Check if a resource is in a shared state"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._state == ResourceState.SHARED or bool(resource._attracted_to)

    async def lock_resource(
        self,
        resource: MagneticResource,
        holder: MagneticResource
    ) -> bool:
        """Lock a resource for exclusive use"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return await resource.lock(holder)

    def is_resource_locked(self, resource: MagneticResource) -> bool:
        """Check if a resource is currently locked"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._state == ResourceState.LOCKED

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

    async def enable_chat(
        self,
        model1: MagneticResource,
        model2: MagneticResource
    ) -> bool:
        """Enable direct communication between models"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during chat setup
            if not self._active:
                self._active = True
            
            # Verify resources are in field
            if not (model1.name in self._resources and model2.name in self._resources):
                raise ValueError("Both models must be in the field")
            
            # Start chat
            success = await model1.attract_to(model2)
            if success:
                # Update states for both models
                model1._state = ResourceState.CHATTING
                model2._state = ResourceState.CHATTING
                # Ensure mutual attraction
                await model2.attract_to(model1)
                self._emit_event(ChatEvent(model1, model2))
            return success
        finally:
            # Restore original activation state
            self._active = was_active

    async def enable_pull(
        self,
        target: MagneticResource,
        source: MagneticResource
    ) -> bool:
        """Enable one-way data flow"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during pull setup
            if not self._active:
                self._active = True
            
            # Verify resources are in field
            if not (target.name in self._resources and source.name in self._resources):
                raise ValueError("Both resources must be in the field")
            
            # Start pull
            success = await target.attract_to(source)
            if success:
                # Update states for both resources
                target._state = ResourceState.PULLING
                source._state = ResourceState.SHARED
                self._emit_event(PullEvent(target, source))
            return success
        finally:
            # Restore original activation state
            self._active = was_active
