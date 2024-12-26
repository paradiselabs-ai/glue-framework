"""GLUE Magnetic Field System"""

import asyncio
from typing import Dict, List, Optional, Set, Type, Callable, Any
from enum import Enum, auto
from dataclasses import dataclass
from collections import defaultdict
from ..core.context import ContextState, InteractionType
from ..core.resource import Resource, ResourceState
from ..core.registry import ResourceRegistry
from .rules import RuleSet, AttractionRule, PolicyPriority, AttractionPolicy

# ==================== Event Types ====================
class FieldEvent:
    """Base class for field events"""
    pass

class ResourceAddedEvent(FieldEvent):
    """Event fired when a resource is added to the field"""
    def __init__(self, resource: Resource):
        self.resource = resource

class ResourceRemovedEvent(FieldEvent):
    """Event fired when a resource is removed from the field"""
    def __init__(self, resource: Resource):
        self.resource = resource

class AttractionEvent(FieldEvent):
    """Event fired when resources are attracted"""
    def __init__(self, source: Resource, target: Resource):
        self.source = source
        self.target = target

class RepulsionEvent(FieldEvent):
    """Event fired when resources are repelled"""
    def __init__(self, source: Resource, target: Resource):
        self.source = source
        self.target = target

class ContextChangeEvent(FieldEvent):
    """Event fired when context changes"""
    def __init__(self, context: ContextState):
        self.context = context

class ChatEvent(FieldEvent):
    """Event fired when models start chatting"""
    def __init__(self, model1: Resource, model2: Resource):
        self.model1 = model1
        self.model2 = model2

class PullEvent(FieldEvent):
    """Event fired when a resource starts pulling from another"""
    def __init__(self, target: Resource, source: Resource):
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
        registry: ResourceRegistry,
        parent: Optional['MagneticField'] = None,
        rules: Optional[RuleSet] = None
    ):
        self.name = name
        self.registry = registry
        self.parent = parent
        self._active = False
        self._event_handlers: Dict[Type[FieldEvent], List[Callable]] = defaultdict(list)
        self._child_fields: List['MagneticField'] = []
        self._current_context: Optional[ContextState] = None
        
        # Field-wide rules
        self._rules = rules or RuleSet(f"{name}_field_rules")
        self._rules.add_rule(AttractionRule(
            name="field_state",
            policy=AttractionPolicy.STATE_BASED,
            priority=PolicyPriority.SYSTEM,
            description="Field-wide state validation"
        ))

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
        resources = self.registry.get_resources_by_category("field:" + self.name)
        for resource in resources:
            await resource.exit_field()
            self.registry.unregister(resource.name)
        
        self._active = False
        self._current_context = None

    async def update_context(self, context: ContextState) -> None:
        """Update field's context and propagate to resources"""
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

    async def add_resource(self, resource: Resource) -> None:
        """Add a resource to the field"""
        if not self._active:
            raise RuntimeError("Cannot add resources to inactive field")
        
        # Enter field and register
        await resource.enter_field(self, self.registry)
        self.registry.register(resource, "field:" + self.name)
        
        # Set current context if available
        if self._current_context:
            await resource.update_context(self._current_context)
        
        # Emit event
        self._emit_event(ResourceAddedEvent(resource))

    async def remove_resource(self, resource: Resource) -> None:
        """Remove a resource from the field"""
        if self.registry.get_resource(resource.name, "field:" + self.name):
            await resource.exit_field()
            self.registry.unregister(resource.name)
            self._emit_event(ResourceRemovedEvent(resource))

    async def attract(
        self,
        source: Resource,
        target: Resource
    ) -> bool:
        """Create attraction between two resources"""
        # Verify resources are in field
        if not (
            self.registry.get_resource(source.name, "field:" + self.name) and
            self.registry.get_resource(target.name, "field:" + self.name)
        ):
            raise ValueError("Both resources must be in the field")
        
        # Check field rules
        if not self._rules.validate(source, target):
            return False
        
        # Create attraction
        success = await source.attract_to(target)
        if success:
            self._emit_event(AttractionEvent(source, target))
        return success

    async def repel(
        self,
        source: Resource,
        target: Resource
    ) -> None:
        """Create repulsion between two resources"""
        # Verify resources are in field
        if not (
            self.registry.get_resource(source.name, "field:" + self.name) and
            self.registry.get_resource(target.name, "field:" + self.name)
        ):
            raise ValueError("Both resources must be in the field")
        
        # Create repulsion
        await source.repel_from(target)
        self._emit_event(RepulsionEvent(source, target))

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

    def get_resource(self, name: str) -> Optional[Resource]:
        """Get a resource by name"""
        return self.registry.get_resource(name, "field:" + self.name)

    def list_resources(self) -> List[str]:
        """List all resources in the field"""
        resources = self.registry.get_resources_by_category("field:" + self.name)
        return [r.name for r in resources]

    def get_attractions(
        self,
        resource: Resource
    ) -> Set[Resource]:
        """Get all resources attracted to the given resource"""
        if not self.registry.get_resource(resource.name, "field:" + self.name):
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._attracted_to.copy()

    def get_repulsions(
        self,
        resource: Resource
    ) -> Set[Resource]:
        """Get all resources repelled by the given resource"""
        if not self.registry.get_resource(resource.name, "field:" + self.name):
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._repelled_by.copy()

    def get_resource_state(
        self,
        resource: Resource
    ) -> ResourceState:
        """Get the current state of a resource"""
        if not self.registry.get_resource(resource.name, "field:" + self.name):
            raise ValueError(f"Resource {resource.name} not in field")
        return resource.state

    async def lock_resource(
        self,
        resource: Resource,
        holder: Resource
    ) -> bool:
        """Lock a resource for exclusive use"""
        if not self.registry.get_resource(resource.name, "field:" + self.name):
            raise ValueError(f"Resource {resource.name} not in field")
        return await resource.lock(holder)

    async def unlock_resource(
        self,
        resource: Resource
    ) -> None:
        """Unlock a resource"""
        if not self.registry.get_resource(resource.name, "field:" + self.name):
            raise ValueError(f"Resource {resource.name} not in field")
        await resource.unlock()

    def __str__(self) -> str:
        resources = self.registry.get_resources_by_category("field:" + self.name)
        status = f"MagneticField({self.name}, resources={len(resources)}"
        if self._current_context:
            status += f", mode={self._current_context.interaction_type.name}"
        status += ")"
        return status

    async def enable_chat(
        self,
        model1: Resource,
        model2: Resource
    ) -> bool:
        """Enable direct communication between models"""
        # Verify resources are in field
        if not (
            self.registry.get_resource(model1.name, "field:" + self.name) and
            self.registry.get_resource(model2.name, "field:" + self.name)
        ):
            raise ValueError("Both models must be in the field")
        
        # Start chat
        success = await model1.attract_to(model2)
        if success:
            model1._state = ResourceState.CHATTING
            model2._state = ResourceState.CHATTING
            self._emit_event(ChatEvent(model1, model2))
        return success

    async def enable_pull(
        self,
        target: Resource,
        source: Resource
    ) -> bool:
        """Enable one-way data flow"""
        # Verify resources are in field
        if not (
            self.registry.get_resource(target.name, "field:" + self.name) and
            self.registry.get_resource(source.name, "field:" + self.name)
        ):
            raise ValueError("Both resources must be in the field")
        
        # Start pull
        success = await target.attract_to(source)
        if success:
            target._state = ResourceState.PULLING
            self._emit_event(PullEvent(target, source))
        return success
