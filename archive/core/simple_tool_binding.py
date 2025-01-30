# src/glue/core/simple_tool_binding.py

"""Simplified Tool Binding Implementation"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Set
from enum import Enum, auto

from .types import AdhesiveType
from .state import ResourceState

@dataclass
class SimpleToolBinding:
    """
    Simplified configuration for binding tools to resources.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Adhesive-based binding types (tape, velcro, glue)
    - Basic resource persistence
    """
    type: AdhesiveType
    use_count: int = 0
    last_used: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    state: ResourceState = ResourceState.IDLE
    resource_pool: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def tape(cls, duration_ms: int = 1800000) -> 'SimpleToolBinding':
        """Create a temporary tape binding with no persistence"""
        return cls(
            type=AdhesiveType.TAPE,
            properties={
                "duration_ms": duration_ms,
                "maintains_context": False
            }
        )
    
    @classmethod
    def velcro(cls, reconnect_attempts: int = 3) -> 'SimpleToolBinding':
        """Create a flexible velcro binding with partial persistence"""
        return cls(
            type=AdhesiveType.VELCRO,
            properties={
                "reconnect_attempts": reconnect_attempts,
                "maintains_context": True,
                "context_duration": "session"
            }
        )
    
    @classmethod
    def glue(cls, strength: float = 1.0) -> 'SimpleToolBinding':
        """Create a permanent glue binding with full persistence"""
        return cls(
            type=AdhesiveType.GLUE,
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
        if self.state == ResourceState.IDLE:
            return False
            
        if self.type == AdhesiveType.VELCRO:
            max_attempts = self.properties.get("reconnect_attempts", 3)
            return self.use_count < max_attempts
            
        return False
    
    def should_break(self) -> bool:
        """Check if binding should break after use"""
        if self.state == ResourceState.IDLE:
            return True
            
        if self.type == AdhesiveType.TAPE:
            duration = self.properties.get("duration_ms", 1800000) / 1000
            if self.last_used:
                elapsed = datetime.now().timestamp() - self.last_used
                return elapsed > duration
                
        return False
    
    def store_resource(self, key: str, data: Any) -> None:
        """Store resource data in binding"""
        if self.type == AdhesiveType.TAPE:
            # No persistence for tape
            return
            
        self.resource_pool[key] = data
    
    def get_resource(self, key: str) -> Optional[Any]:
        """Get stored resource data"""
        return self.resource_pool.get(key)
    
    def clear_resources(self) -> None:
        """Clear all stored resources"""
        self.resource_pool.clear()
    
    def use(self) -> None:
        """Record binding usage and update state"""
        # Update usage stats
        self.use_count += 1
        self.last_used = datetime.now().timestamp()
        
        # Update state
        if self.should_break():
            self.state = ResourceState.IDLE
            self.clear_resources()
    
    def bind(self) -> None:
        """Initialize binding"""
        if self.state != ResourceState.IDLE:
            raise ValueError("Binding already initialized")
            
        self.state = ResourceState.ACTIVE
    
    def unbind(self) -> None:
        """Clean up binding"""
        self.clear_resources()
        self.state = ResourceState.IDLE
    
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
        return (
            f"SimpleToolBinding({self.type.name}: "
            f"strength={self.get_strength():.2f}, "
            f"state={self.state.name})"
        )
