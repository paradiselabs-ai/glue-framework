"""GLUE Resource Base System"""

import asyncio
from typing import Dict, List, Optional, Set, Any, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from .state import StateManager
from .registry import ResourceRegistry
from ..magnetic.rules import RuleSet, AttractionRule, PolicyPriority, AttractionPolicy

class ResourceState(Enum):
    """States a resource can be in"""
    IDLE = auto()      # Not currently in use
    ACTIVE = auto()    # Currently in use
    LOCKED = auto()    # Cannot be used by others
    SHARED = auto()    # Being shared between resources
    CHATTING = auto()  # In direct model-to-model communication
    PULLING = auto()   # Receiving data only

@dataclass
class ResourceMetadata:
    """Metadata for a resource"""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    use_count: int = 0
    tags: Set[str] = field(default_factory=set)
    category: str = "default"
    properties: Dict[str, Any] = field(default_factory=dict)

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
        rules: Optional[RuleSet] = None
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
            description="Default state-based validation"
        ))
        
        # Registry reference
        self._registry: Optional[ResourceRegistry] = None
    
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
    
    async def enter_field(self, field: 'MagneticField', registry: Optional[ResourceRegistry] = None) -> None:
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
            
            # Reset state
            async with self._state_change_lock:
                self._state = ResourceState.IDLE
                self._lock_holder = None
                self._context = None
            
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
    
    async def attract_to(self, other: 'Resource') -> bool:
        """Create attraction to another resource"""
        # Check rule validation first
        if not self._rules.validate(self, other):
            return False
            
        # Then check basic attraction rules
        if not self.can_attract(other):
            return False
            
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