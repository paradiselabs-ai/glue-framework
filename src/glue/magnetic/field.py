"""GLUE Magnetic Field System"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Type, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass
from collections import defaultdict
from ..core.state import StateManager
from ..core.types import ResourceState, MagneticResource, AdhesiveType
from .rules import RuleSet, AttractionRule, PolicyPriority, AttractionPolicy

if TYPE_CHECKING:
    from ..core.context import ContextState, InteractionType
    from ..core.registry import ResourceRegistry
    from ..core.model import Model
    from ..tools.simple_base import SimpleBaseTool as BaseTool

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
        
class PushEvent(FieldEvent):
    """Event fired when a resource starts pushing to another"""
    def __init__(self, source: MagneticResource, target: MagneticResource):
        self.source = source
        self.target = target

# ==================== Main Class ====================
class MagneticField:
    """
    Manages interaction boundaries and information flow between resources.
    
    Key Responsibilities:
    - Define interaction guidelines
    - Control resource communication
    - Manage context-aware state transitions
    - Provide event-driven resource tracking
    
    Interaction Patterns:
    - Bidirectional attraction (><)
    - Unidirectional push (->)
    - Unidirectional pull (<-)
    - Repulsion (<>)
    
    Example:
        ```python
        registry = ResourceRegistry()
        async with MagneticField("research", registry) as field:
            await field.add_resource(researcher)
            await field.add_resource(assistant)
            await field.enable_chat(researcher, assistant)
        ```
    """
    def __init__(
        self,
        name: str,
        registry: 'ResourceRegistry',
        parent: Optional['MagneticField'] = None,
        rules: Optional[RuleSet] = None,
        auto_bind: bool = True,
        is_pull_team: bool = False
    ):  
        self.name = name
        self.registry = registry
        self.parent = parent
        self._active = False
        self._event_handlers = defaultdict(list)
        self._child_fields = []
        self._current_context = None
        self._resources = {}
        self._state_manager = StateManager()
        self._chat_handler = None  # First model becomes chat handler
        self._memory = []  # Field memory
        
        # Team configuration
        self.is_pull_team = is_pull_team  # Whether this team can pull from others
        self.auto_bind = auto_bind  # Enable automatic binding
        
        # Initialize logger
        self.logger = logging.getLogger(f"glue.magnetic.field.{name}")

        # Configure valid transitions
        self._setup_transitions()

        # Field-wide rules
        self._rules = rules or RuleSet(f"{name}_field_rules")
        self._rules.add_rule(AttractionRule(
            name="interaction_boundary",
            policy=AttractionPolicy.STATE_BASED,
            priority=PolicyPriority.SYSTEM,
            state_validator=lambda s1, s2: (
                s1 in {ResourceState.IDLE, ResourceState.ACTIVE} and
                s2 in {ResourceState.IDLE, ResourceState.ACTIVE}
            ),  # Only validate IDLE/ACTIVE states
            description="Manage resource interaction boundaries"
        ))

    def _setup_transitions(self):
        """Configure valid state transitions"""
        # Define valid state transitions
        VALID_TRANSITIONS = {
            ResourceState.IDLE: {
                ResourceState.ACTIVE: self._idle_to_active,
                ResourceState.CHATTING: self._idle_to_chatting,
                ResourceState.PULLING: self._idle_to_pulling
            },
            ResourceState.ACTIVE: {
                ResourceState.IDLE: self._active_to_idle,
                ResourceState.CHATTING: self._active_to_chatting,
                ResourceState.PULLING: self._active_to_pulling
            },
            ResourceState.CHATTING: {
                ResourceState.IDLE: self._chatting_to_idle,
                ResourceState.ACTIVE: self._chatting_to_active
            },
            ResourceState.PULLING: {
                ResourceState.IDLE: self._pulling_to_idle,
                ResourceState.ACTIVE: self._pulling_to_active
            }
        }
        
        # Register transitions with state manager
        for from_state, transitions in VALID_TRANSITIONS.items():
            for to_state, handler in transitions.items():
                self._state_manager.add_transition(from_state, to_state, handler)

    async def _idle_to_active(self, resource: MagneticResource) -> None:
        """Handle transition from IDLE to ACTIVE"""
        # Initialize workspace if needed
        if hasattr(resource, '_workspace') and not resource._workspace:
            await resource.initialize_workspace()

    async def _active_to_idle(self, resource: MagneticResource) -> None:
        """Handle transition from ACTIVE to IDLE"""
        # Break all attractions
        for other in list(resource._attracted_to):
            await self.break_attraction(resource, other)
        # Clean up workspace
        if hasattr(resource, '_workspace'):
            await resource.cleanup_workspace()

    async def _idle_to_chatting(self, resource: MagneticResource) -> None:
        """Handle transition from IDLE to CHATTING"""
        await self._idle_to_active(resource)  # Initialize workspace
        # Set up chat context
        if hasattr(resource, 'prepare_chat'):
            await resource.prepare_chat()

    async def _active_to_chatting(self, resource: MagneticResource) -> None:
        """Handle transition from ACTIVE to CHATTING"""
        # Set up chat context
        if hasattr(resource, 'prepare_chat'):
            await resource.prepare_chat()

    async def _chatting_to_idle(self, resource: MagneticResource) -> None:
        """Handle transition from CHATTING to IDLE"""
        await self._active_to_idle(resource)  # Clean up workspace
        # Clean up chat context
        if hasattr(resource, 'cleanup_chat'):
            await resource.cleanup_chat()

    async def _chatting_to_active(self, resource: MagneticResource) -> None:
        """Handle transition from CHATTING to ACTIVE"""
        # Clean up chat context
        if hasattr(resource, 'cleanup_chat'):
            await resource.cleanup_chat()

    async def _idle_to_pulling(self, resource: MagneticResource) -> None:
        """Handle transition from IDLE to PULLING"""
        await self._idle_to_active(resource)  # Initialize workspace
        # Set up pull context
        if hasattr(resource, 'prepare_pull'):
            await resource.prepare_pull()

    async def _active_to_pulling(self, resource: MagneticResource) -> None:
        """Handle transition from ACTIVE to PULLING"""
        # Set up pull context
        if hasattr(resource, 'prepare_pull'):
            await resource.prepare_pull()

    async def _pulling_to_idle(self, resource: MagneticResource) -> None:
        """Handle transition from PULLING to IDLE"""
        await self._active_to_idle(resource)  # Clean up workspace
        # Clean up pull context
        if hasattr(resource, 'cleanup_pull'):
            await resource.cleanup_pull()

    async def _pulling_to_active(self, resource: MagneticResource) -> None:
        """Handle transition from PULLING to ACTIVE"""
        # Clean up pull context
        if hasattr(resource, 'cleanup_pull'):
            await resource.cleanup_pull()

    async def break_attraction(
        self,
        source: MagneticResource,
        target: MagneticResource
    ) -> None:
        """Break an existing attraction between resources"""
        if source.name not in self._resources:
            raise ValueError(f"Source resource {source.name} not in field")
        if target.name not in self._resources:
            raise ValueError(f"Target resource {target.name} not in field")
            
        # Remove attraction
        if target in source._attracted_to:
            source._attracted_to.remove(target)
            
        # Emit event
        self._emit_event(RepulsionEvent(source, target))

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
        errors = []
        
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during cleanup
            if not self._active:
                self._active = True
            
            # Clean up child fields first
            for child in self._child_fields:
                try:
                    await child.cleanup()
                except Exception as e:
                    errors.append(f"Failed to clean up child field {child.name}: {str(e)}")
            self._child_fields.clear()
            
            # Clean up resources while field is still active
            resources = self.registry.get_resources_by_category("field:" + self.name)
            for resource in resources:
                try:
                    # Break all attractions first
                    for other in list(resource._attracted_to):
                        try:
                            await self.break_attraction(resource, other)
                        except Exception as e:
                            errors.append(f"Failed to break attraction between {resource.name} and {other.name}: {str(e)}")
                    
                    # Clean up resource
                    await resource.exit_field()
                    self.registry.unregister(resource.name)
                except Exception as e:
                    errors.append(f"Failed to clean up resource {resource.name}: {str(e)}")
            
            # Clear context and memory
            self._current_context = None
            self._memory.clear()
            
            # Clear resources and event handlers
            self._resources.clear()
            self._event_handlers.clear()
            
            # Report any errors that occurred during cleanup
            if errors:
                error_msg = "\n".join(errors)
                self.logger.error(f"Cleanup errors:\n{error_msg}")
                if len(errors) > 1:
                    raise RuntimeError(f"Multiple cleanup errors occurred:\n{error_msg}")
                raise RuntimeError(errors[0])
                
        finally:
            # Restore original activation state
            self._active = was_active

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

    def _determine_binding_type(
        self,
        source: MagneticResource,
        target: MagneticResource,
        cross_team: bool = False
    ) -> AdhesiveType:
        """Determine appropriate binding type"""
        # If either resource is sticky, use GLUE
        if (hasattr(source, 'sticky') and source.sticky) or \
           (hasattr(target, 'sticky') and target.sticky):
            return AdhesiveType.GLUE
            
        # Cross-team bindings use TAPE
        if cross_team:
            return AdhesiveType.TAPE
            
        # Default to VELCRO for team-internal bindings
        return AdhesiveType.VELCRO
        
    async def add_resource(
        self,
        resource: MagneticResource,
        is_lead: bool = False,
        auto_bind: bool = True
    ) -> None:
        """
        Add a resource to the field
        
        Args:
            resource: Resource to add
            is_lead: Whether this resource is the team lead
        """
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
            
            # If auto_bind is enabled, setup team bindings
            if auto_bind and isinstance(resource, Model):
                # Auto-bind to other team members
                for other in self._resources.values():
                    if isinstance(other, Model) and other != resource:
                        # Determine binding type
                        binding_type = self._determine_binding_type(resource, other)
                        
                        # Enable chat between team members
                        await self.enable_chat(resource, other)
                        
                        # Share tools with appropriate binding
                        for tool_name, tool in self._resources.items():
                            if isinstance(tool, BaseTool):
                                if hasattr(resource, 'add_tool'):
                                    resource.add_tool(tool_name, tool, binding_type)
                                if hasattr(other, 'add_tool'):
                                    other.add_tool(tool_name, tool, binding_type)
                
                # Set as chat handler if first model or lead
                if (
                    isinstance(resource, Model) and
                    (is_lead or not self._chat_handler)
                ):
                    self._chat_handler = resource
                
                # Set current context if available
                if self._current_context:
                    await resource.update_context(self._current_context)
                
                # Emit event
                self._emit_event(ResourceAddedEvent(resource))
        except Exception as e:
            # Cleanup on error
            if resource.name in self._resources:
                del self._resources[resource.name]
            if self.registry.get_resource(resource.name, "field:" + self.name):
                await resource.exit_field()
                self.registry.unregister(resource.name)
            raise  # Re-raise the exception
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
        """Enable interaction between two resources"""
        # Save current activation state
        was_active = self._active

        try:
            # Ensure field is active during interaction setup
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
            await self._state_manager.transition(source, ResourceState.ACTIVE, self._current_context)
            await self._state_manager.transition(target, ResourceState.ACTIVE, self._current_context)

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
        name: str,
        auto_bind: Optional[bool] = None,
        is_pull_team: Optional[bool] = None
    ) -> 'MagneticField':
        """Create a child field that inherits from this field"""
        child = MagneticField(
            name=name,
            registry=self.registry,
            parent=self,
            rules=self._rules.copy(),  # Inherit parent rules
            auto_bind=auto_bind if auto_bind is not None else self.auto_bind,
            is_pull_team=is_pull_team if is_pull_team is not None else False
        )
        child._active = True
        if self._current_context:
            child._current_context = self._current_context
        self._child_fields.append(child)
        return child
        
    def get_child_field(self, name: str) -> Optional['MagneticField']:
        """Get a child field by name"""
        for child in self._child_fields:
            if child.name == name:
                return child
        return None
        
    def _is_repelled(self, other: 'MagneticField') -> bool:
        """Check if this field is repelled from another"""
        # Check if there's a repulsion in either direction
        if not self.parent or not other.parent:
            return False
            
        workflow = self.parent.workflow
        if not workflow:
            return False
            
        return (
            (self.name, other.name) in workflow.repulsions or
            (other.name, self.name) in workflow.repulsions
        )

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
        
    def _calculate_field_strength(self) -> float:
        """Calculate current field strength"""
        strength = 1.0  # Base strength
        
        # Adjust based on team expertise (number of successful interactions)
        success_rate = sum(1 for m in self._memory 
                         if m.get('type') == 'response' and not m.get('error'))
        total_interactions = len([m for m in self._memory 
                               if m.get('type') in ('response', 'pulled_response')])
        if total_interactions > 0:
            strength *= (0.5 + 0.5 * (success_rate / total_interactions))
        
        # Adjust based on tool capabilities
        available_tools = len([r for r in self._resources.values() 
                             if isinstance(r, BaseTool)])
        strength *= (1.0 + 0.1 * available_tools)  # 10% boost per tool
        
        # Adjust based on team workload
        active_resources = len([r for r in self._resources.values() 
                              if r._state != ResourceState.IDLE])
        if active_resources > 0:
            strength *= (1.0 - 0.1 * active_resources)  # 10% penalty per active resource
            
        return min(strength, 2.0)  # Cap at 2x base strength
        
    async def handles_intent(self, prompt: str) -> float:
        """Return how strongly this field attracts the prompt"""
        if not self._chat_handler:
            return 0.0
            
        # Let chat handler analyze the prompt
        analysis = await self._chat_handler.analyze_intent(
            prompt,
            context={
                'field_name': self.name,
                'available_tools': [t.description for t in self._resources.values() if isinstance(t, BaseTool)],
                'team_members': [m.name for m in self._resources.values() if isinstance(m, Model)],
                'field_strength': self._calculate_field_strength(),
                'recent_memory': self._memory[-5:] if self._memory else []
            }
        )
        
        # Adjust score based on field strength
        analysis.score *= self._calculate_field_strength()
        
        # Direct addressing is still explicit
        for resource in self._resources.values():
            if resource.name.lower() in prompt.lower():
                analysis.score = max(analysis.score, 1.0)  # Ensure at least base strength
                
        return min(analysis.score, 2.0)  # Cap at 2x base strength
        
    async def process_prompt(self, prompt: str) -> str:
        """Process a prompt in this field"""
        if not self._chat_handler:
            raise RuntimeError("No chat handler available")
            
        # Store in memory
        self._memory.append({
            'type': 'prompt',
            'content': prompt,
            'timestamp': datetime.now()
        })
        
        # Get recent context
        context = self._memory[-5:] if self._memory else []
        
        try:
            # Let chat handler process with tool access
            response = await self._chat_handler.process(
                prompt,
                context={
                    **context,
                    'tools': {
                        name: tool for name, tool in self._resources.items()
                        if isinstance(tool, BaseTool) and
                        hasattr(self._chat_handler, '_tools') and
                        name in self._chat_handler._tools
                    }
                }
            )
            
            # Store response
            self._memory.append({
                'type': 'response',
                'model': self._chat_handler.name,
                'content': response,
                'timestamp': datetime.now()
            })
            
            return response
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error processing prompt: {str(e)}")
            
            # If this is the designated pull team, try pulling from other teams
            if hasattr(self, 'is_pull_team') and self.is_pull_team:
                self.logger.info(f"Pull team {self.name} attempting to pull from other teams")
                
                # Try to pull from each non-repelled team
                for other_field in self.parent._child_fields if self.parent else []:
                    if other_field != self and not self._is_repelled(other_field):
                        try:
                            # Enable pull and try processing
                            await self.enable_field_pull(other_field)
                            response = await other_field.process_prompt(prompt)
                            
                            # Store pulled response
                            self._memory.append({
                                'type': 'pulled_response',
                                'source': other_field.name,
                                'content': response,
                                'timestamp': datetime.now()
                            })
                            
                            return response
                        except Exception as pull_error:
                            self.logger.debug(f"Pull from {other_field.name} failed: {str(pull_error)}")
                            continue
            
            # If pull fails or not pull team, raise original error
            raise
        
    def get_memory(
        self,
        limit: int = 100,
        include_pulled: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get field memory up to limit
        
        Args:
            limit: Maximum number of memories to return
            include_pulled: Whether to include pulled memories
        """
        if include_pulled:
            return self._memory[-limit:]
            
        # Filter out pulled memories if not included
        return [
            m for m in self._memory[-limit:]
            if m.get('type') != 'pulled_response'
        ]

    def is_resource_active(self, resource: MagneticResource) -> bool:
        """Check if a resource is in active state"""
        if resource.name not in self._resources:
            raise ValueError(f"Resource {resource.name} not in field")
        return resource._state == ResourceState.ACTIVE or bool(resource._attracted_to)

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
                await self._state_manager.transition(model1, ResourceState.ACTIVE)
                await self._state_manager.transition(model2, ResourceState.ACTIVE)
                # Ensure mutual attraction
                await model2.attract_to(model1)
                self._emit_event(ChatEvent(model1, model2))
            return success
        finally:
            # Restore original activation state
            self._active = was_active

    async def enable_field_pull(
        self,
        source_field: 'MagneticField'
    ) -> bool:
        """Enable pulling from another field"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during pull setup
            if not self._active:
                self._active = True
            
            # Enable pull fallback
            self.pull_fallback = True
            
            # Get chat handlers from both fields
            target_handler = self._chat_handler
            source_handler = source_field._chat_handler
            
            if not target_handler or not source_handler:
                return False
            
            # Enable pull between chat handlers
            return await self.enable_pull(target_handler, source_handler)
        finally:
            # Restore original activation state
            self._active = was_active
            
    async def enable_pull(
        self,
        target: MagneticResource,
        source: MagneticResource
    ) -> bool:
        """Enable one-way data flow from source to target"""
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
                await self._state_manager.transition(target, ResourceState.ACTIVE)
                await self._state_manager.transition(source, ResourceState.ACTIVE)
                self._emit_event(PullEvent(target, source))
            return success
        finally:
            # Restore original activation state
            self._active = was_active

    async def enable_push(
        self,
        source: MagneticResource,
        target: MagneticResource
    ) -> bool:
        """Enable one-way data flow from source to target"""
        # Save current activation state
        was_active = self._active
        
        try:
            # Ensure field is active during push setup
            if not self._active:
                self._active = True
            
            # Verify resources are in field
            if not (source.name in self._resources and target.name in self._resources):
                raise ValueError("Both resources must be in the field")
            
            # Start push
            success = await source.attract_to(target)
            if success:
                # Update states for both resources
                await self._state_manager.transition(source, ResourceState.ACTIVE)
                await self._state_manager.transition(target, ResourceState.ACTIVE)
                self._emit_event(PushEvent(source, target))
            return success
        finally:
            # Restore original activation state
            self._active = was_active
