"""GLUE Resource Base System"""

import asyncio
from typing import Dict, List, Optional, Set, Any, Type, Callable, TYPE_CHECKING
from datetime import datetime

from .types import ResourceState, ResourceMetadata
from .binding import AdhesiveType
from .tool_binding import ToolBinding
from ..magnetic.rules import RuleSet, AttractionRule, PolicyPriority, AttractionPolicy

if TYPE_CHECKING:
    from .state import StateManager
    from .registry import ResourceRegistry
    from ..magnetic.field import MagneticField
    from .context import ContextState

class Resource:
    """
    Base class for all GLUE resources.
    
    This provides the foundation for:
    - State management
    - Field interactions
    - Context awareness
    - Resource tracking
    - Rule validation
    - Registry integration
    """
    
    def __init__(
        self,
        name: str,
        category: str = "default",
        tags: Optional[Set[str]] = None,
        rules: Optional[RuleSet] = None,
        tool_bindings: Optional[Dict[str, AdhesiveType]] = None
    ):
        """Initialize resource"""
        self.name = name
        self._state = ResourceState.IDLE
        self._field: Optional['MagneticField'] = None
        self._context: Optional['ContextState'] = None
        self._lock_holder: Optional['Resource'] = None
        self._attracted_to: Set['Resource'] = set()
        self._repelled_by: Set['Resource'] = set()
        
        # Metadata for tracking
        self.metadata = ResourceMetadata(
            category=category,
            tags=tags or set()
        )
        
        # Event handling
        self._event_handlers: Dict[str, List[callable]] = {}
        self._state_change_lock = asyncio.Lock()
        
        # Rule system
        self._rules = rules or RuleSet(f"{name}_rules")
        self._rules.add_rule(AttractionRule(
            name="default_state",
            policy=AttractionPolicy.STATE_BASED,
            priority=PolicyPriority.SYSTEM,
            state_validator=lambda s1, s2: s1 in [ResourceState.IDLE, ResourceState.SHARED] and 
                                         s2 in [ResourceState.IDLE, ResourceState.SHARED],
            description="Default state-based validation"
        ))
        
        # Registry reference
        self._registry: Optional['ResourceRegistry'] = None
        
        # Tool binding management
        self._tool_bindings: Dict[str, ToolBinding] = {}
        if tool_bindings:
            for tool_name, strength in tool_bindings.items():
                self.bind_tool(tool_name, strength)
    
    @property
    def state(self) -> ResourceState:
        """Get current state"""
        return self._state
    
    @property
    def field(self) -> Optional['MagneticField']:
        """Get current field"""
        return self._field
    
    @property
    def context(self) -> Optional['ContextState']:
        """Get current context"""
        return self._context
    
    async def enter_field(self, field: 'MagneticField', registry: Optional['ResourceRegistry'] = None) -> None:
        """Enter a magnetic field"""
        if self._field and self._field != field:
            await self.exit_field()
            
        self._field = field
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
        if self._field:
            # Clean up attractions/repulsions
            for other in list(self._attracted_to):
                await self.break_attraction(other)
            for other in list(self._repelled_by):
                await self.break_repulsion(other)
            
            old_field = self._field
            self._field = None
            
            # Reset state and cleanup attributes
            async with self._state_change_lock:
                self._state = ResourceState.IDLE
                self._lock_holder = None
                self._context = None
                if hasattr(self, "_attract_mode"):
                    delattr(self, "_attract_mode")
            
            await self._emit_event("field_exit", old_field)
            
            # Notify registry
            if self._registry:
                self._registry._notify_observers("field_exit", {
                    "resource": self.name,
                    "field": old_field.name
                })
                self._registry = None
    
    async def update_context(self, context: 'ContextState') -> None:
        """Update resource context"""
        old_context = self._context
        self._context = context
        
        # Update rules based on context
        if hasattr(context, "rules"):
            self._rules = context.rules
        
        await self._emit_event("context_change", {
            "old": old_context,
            "new": context
        })
        
        # Notify registry
        if self._registry:
            self._registry._notify_observers("context_change", {
                "resource": self.name,
                "old": old_context,
                "new": context
            })
    
    def bind_tool(self, tool_name: str, binding_type: AdhesiveType) -> None:
        """
        Bind a tool with specified adhesive type
        
        Args:
            tool_name: Name of tool to bind
            binding_type: Type of adhesive binding to use
        """
        if binding_type == AdhesiveType.TAPE:
            binding = ToolBinding.tape()
        elif binding_type == AdhesiveType.VELCRO:
            binding = ToolBinding.velcro()
        elif binding_type == AdhesiveType.GLUE:
            binding = ToolBinding.glue()
        elif binding_type == AdhesiveType.MAGNET:
            binding = ToolBinding.magnet()
        else:
            raise ValueError(f"Invalid binding type: {binding_type}")
            
        self._tool_bindings[tool_name] = binding
    
    def get_tool_binding(self, tool_name: str) -> Optional[ToolBinding]:
        """Get binding configuration for a tool"""
        return self._tool_bindings.get(tool_name)
    
    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """Use a tool with binding rules"""
        binding = self.get_tool_binding(tool_name)
        if not binding:
            raise ValueError(f"No binding found for tool: {tool_name}")
        
        # Get tool from registry
        if not self._registry:
            raise RuntimeError("No registry available")
        tool = self._registry.get_resource(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        try:
            # Add context for GLUE bindings
            if binding.maintains_context():
                kwargs["context"] = binding.context
            
            # Execute tool
            result = await tool.execute(**kwargs)
            
            # Update binding state
            binding.use_count += 1
            binding.last_used = datetime.now().timestamp()
            
            # Store context for GLUE bindings
            if binding.maintains_context():
                binding.context.update(result.get("context", {}))
            
            # Break TAPE bindings after use
            if binding.should_break():
                await self.break_attraction(tool)
            
            return result
            
        except Exception as e:
            # Handle reconnection for VELCRO bindings
            if binding.can_reconnect():
                # Could implement retry logic here
                pass
            raise
    
    async def attract_to(self, other: 'Resource') -> bool:
        """Create attraction to another resource"""
        # Check rule validation first
        if not self._rules.validate(self, other):
            return False
            
        # Then check basic attraction rules
        if not self.can_attract(other):
            return False
        
        # Check tool bindings (skip in test environments)
        if other.metadata.category == "tool" and not getattr(self, "_skip_binding_check", False):
            binding = self.get_tool_binding(other.name)
            if not binding:
                return False  # No binding configured
        
        # Create attraction
        self._attracted_to.add(other)
        other._attracted_to.add(self)
        
        # Update states
        if self._state == ResourceState.IDLE:
            self._state = ResourceState.SHARED
        if other._state == ResourceState.IDLE:
            other._state = ResourceState.SHARED
        
        # Emit events
        await self._emit_event("attraction", other)
        await other._emit_event("attraction", self)
        
        # Notify registry
        if self._registry:
            self._registry._notify_observers("attraction", {
                "source": self.name,
                "target": other.name
            })
        
        return True
    
    async def repel_from(self, other: 'Resource') -> None:
        """Create repulsion from another resource"""
        self._repelled_by.add(other)
        other._repelled_by.add(self)
        
        # Break any existing attractions
        if other in self._attracted_to:
            await self.break_attraction(other)
            
        await self._emit_event("repulsion", other)
        await other._emit_event("repulsion", self)
        
        # Notify registry
        if self._registry:
            self._registry._notify_observers("repulsion", {
                "source": self.name,
                "target": other.name
            })
    
    async def break_attraction(self, other: 'Resource') -> None:
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
    
    async def break_repulsion(self, other: 'Resource') -> None:
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
    
    def can_attract(self, other: 'Resource') -> bool:
        """Check if attraction is allowed"""
        # Check repulsions
        if other in self._repelled_by or self in other._repelled_by:
            return False
            
        # Check locks
        if (self._state == ResourceState.LOCKED and self._lock_holder != other or
            other._state == ResourceState.LOCKED and other._lock_holder != self):
            return False
            
        # Check field compatibility
        if self._field and other._field and self._field != other._field:
            return False
            
        # Check context compatibility
        if self._context and other._context:
            if self._context != other._context:
                return False
            
        return True
    
    async def lock(self, holder: 'Resource') -> bool:
        """Lock resource for exclusive use"""
        if self._state == ResourceState.LOCKED:
            return False
            
        async with self._state_change_lock:
            # Break attractions except with holder
            for other in list(self._attracted_to):
                if other != holder:
                    await self.break_attraction(other)
                    
            self._state = ResourceState.LOCKED
            self._lock_holder = holder
            await self._emit_event("locked", holder)
            
            # Notify registry
            if self._registry:
                self._registry._notify_observers("locked", {
                    "resource": self.name,
                    "holder": holder.name
                })
            
        return True
    
    async def unlock(self) -> None:
        """Unlock resource"""
        if self._state == ResourceState.LOCKED:
            async with self._state_change_lock:
                old_holder = self._lock_holder
                self._state = ResourceState.IDLE
                self._lock_holder = None
                await self._emit_event("unlocked", old_holder)
                
                # Notify registry
                if self._registry:
                    self._registry._notify_observers("unlocked", {
                        "resource": self.name,
                        "holder": old_holder.name if old_holder else None
                    })
    
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
    
    def __str__(self) -> str:
        """String representation"""
        status = [
            f"Resource({self.name})",
            f"State: {self._state.name}",
            f"Field: {self._field.name if self._field else 'None'}",
            f"Attractions: {len(self._attracted_to)}",
            f"Repulsions: {len(self._repelled_by)}"
        ]
        return " | ".join(status)
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"Resource(name='{self.name}', "
            f"state={self._state.name}, "
            f"field={self._field.name if self._field else 'None'}, "
            f"context={self._context})"
        )
