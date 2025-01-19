"""Tool binding implementation for GLUE"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Set
from enum import Enum, auto

from .types import AdhesiveType
from .types import BindingState
from ..magnetic.rules import InteractionPattern

class ToolBindingState(Enum):
    """Tool-specific binding states"""
    UNBOUND = auto()      # Not bound to any resource
    BOUND = auto()        # Bound and ready
    IN_USE = auto()       # Currently being used
    DEGRADED = auto()     # Bound but weakened
    FAILED = auto()       # Failed and needs cleanup

@dataclass
class ToolBinding:
    """
    Configuration for binding tools to resources.
    
    Features:
    - Adhesive-based binding types (tape, velcro, glue)
    - Interaction pattern support (><, ->, <-, <>)
    - Resource persistence and pooling
    - State management and transitions
    - Context preservation
    
    Binding Types:
    - GLUE: Full persistence, maintains context
    - VELCRO: Partial persistence, reconnectable
    - TAPE: No persistence, temporary use
    """
    type: AdhesiveType
    use_count: int = 0
    last_used: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    patterns: Set[InteractionPattern] = field(default_factory=set)
    state: ToolBindingState = ToolBindingState.UNBOUND
    resource_pool: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def tape(
        cls,
        patterns: Optional[Set[InteractionPattern]] = None,
        duration_ms: int = 1800000
    ) -> 'ToolBinding':
        """
        Create a temporary tape binding with no persistence
        
        Args:
            patterns: Allowed interaction patterns
            duration_ms: Duration in milliseconds
        """
        return cls(
            type=AdhesiveType.TAPE,
            patterns=patterns or {InteractionPattern.ATTRACT},
            properties={
                "duration_ms": duration_ms,
                "maintains_context": False
            }
        )
    
    @classmethod
    def velcro(
        cls,
        patterns: Optional[Set[InteractionPattern]] = None,
        reconnect_attempts: int = 3
    ) -> 'ToolBinding':
        """
        Create a flexible velcro binding with partial persistence
        
        Args:
            patterns: Allowed interaction patterns
            reconnect_attempts: Max reconnection attempts
        """
        return cls(
            type=AdhesiveType.VELCRO,
            patterns=patterns or {
                InteractionPattern.ATTRACT,
                InteractionPattern.PUSH,
                InteractionPattern.PULL
            },
            properties={
                "reconnect_attempts": reconnect_attempts,
                "maintains_context": True,
                "context_duration": "session"
            }
        )
    
    @classmethod
    def glue(
        cls,
        patterns: Optional[Set[InteractionPattern]] = None,
        strength: float = 1.0
    ) -> 'ToolBinding':
        """
        Create a permanent glue binding with full persistence
        
        Args:
            patterns: Allowed interaction patterns
            strength: Initial binding strength
        """
        return cls(
            type=AdhesiveType.GLUE,
            patterns=patterns or {InteractionPattern.ATTRACT},
            properties={
                "strength": strength,
                "maintains_context": True,
                "context_duration": "permanent"
            }
        )
    
    def maintains_context(self) -> bool:
        """Check if binding maintains context between uses"""
        return self.properties.get("maintains_context", False)
    
    def can_reconnect(self) -> bool:
        """Check if binding can reconnect after failure"""
        if self.state == ToolBindingState.FAILED:
            return False
            
        if self.type == AdhesiveType.VELCRO:
            max_attempts = self.properties.get("reconnect_attempts", 3)
            return self.use_count < max_attempts
            
        return False
    
    def should_break(self) -> bool:
        """Check if binding should break after use"""
        if self.state == ToolBindingState.FAILED:
            return True
            
        if self.type == AdhesiveType.TAPE:
            duration = self.properties.get("duration_ms", 1800000) / 1000  # convert to seconds
            if self.last_used:
                elapsed = datetime.now().timestamp() - self.last_used
                return elapsed > duration
                
        return False
    
    def get_context_duration(self) -> str:
        """Get the context persistence duration"""
        return self.properties.get("context_duration", "none")
    
    def can_use_pattern(self, pattern: InteractionPattern) -> bool:
        """
        Check if pattern can be used with this binding
        
        Args:
            pattern: Interaction pattern to check
        """
        return pattern in self.patterns
    
    def store_resource(self, key: str, data: Any) -> None:
        """
        Store resource data in binding
        
        Args:
            key: Resource identifier
            data: Resource data
        """
        if self.type == AdhesiveType.TAPE:
            # No persistence for tape
            return
            
        self.resource_pool[key] = data
    
    def get_resource(self, key: str) -> Optional[Any]:
        """
        Get stored resource data
        
        Args:
            key: Resource identifier
        """
        return self.resource_pool.get(key)
    
    def clear_resources(self) -> None:
        """Clear all stored resources"""
        self.resource_pool.clear()
    
    def use(self, pattern: Optional[InteractionPattern] = None) -> None:
        """
        Record binding usage and update state
        
        Args:
            pattern: Interaction pattern being used
        """
        # Validate pattern
        if pattern and not self.can_use_pattern(pattern):
            raise ValueError(f"Pattern {pattern} not allowed for this binding")
            
        # Update usage stats
        self.use_count += 1
        self.last_used = datetime.now().timestamp()
        
        # Update state
        if self.should_break():
            self.state = ToolBindingState.FAILED
            self.clear_resources()
        elif self.type == AdhesiveType.VELCRO:
            max_attempts = self.properties.get("reconnect_attempts", 3)
            if self.use_count >= max_attempts / 2:
                self.state = ToolBindingState.DEGRADED
    
    def bind(self) -> None:
        """Initialize binding"""
        if self.state != ToolBindingState.UNBOUND:
            raise ValueError("Binding already initialized")
            
        self.state = ToolBindingState.BOUND
    
    def unbind(self) -> None:
        """Clean up binding"""
        self.clear_resources()
        self.state = ToolBindingState.UNBOUND
    
    def get_strength(self) -> float:
        """Get current binding strength"""
        base_strength = self.properties.get("strength", 1.0)
        
        if self.type == AdhesiveType.TAPE:
            # Tape weakens over time
            duration = self.properties.get("duration_ms", 1800000) / 1000
            if self.last_used:
                elapsed = datetime.now().timestamp() - self.last_used
                remaining = max(0, duration - elapsed)
                return base_strength * (remaining / duration)
                
        elif self.type == AdhesiveType.VELCRO:
            # Velcro weakens with each use
            max_attempts = self.properties.get("reconnect_attempts", 3)
            return base_strength * (1 - (self.use_count / max_attempts))
            
        return base_strength
    
    def __str__(self) -> str:
        patterns = ", ".join(p.value for p in self.patterns)
        return (
            f"ToolBinding({self.type.name}: "
            f"patterns=[{patterns}], "
            f"strength={self.get_strength():.2f}, "
            f"state={self.state.name})"
        )
