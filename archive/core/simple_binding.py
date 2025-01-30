# src/glue/core/simple_binding.py

"""Simplified binding system for GLUE"""

from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from ..magnetic.rules import InteractionPattern
from .types import AdhesiveType, ResourceState

@dataclass
class SimpleBindingConfig:
    """Configuration for a binding between models"""
    type: AdhesiveType
    source: str  # source model name
    target: str  # target model name
    patterns: Set[InteractionPattern] = field(default_factory=set)  # Allowed interaction patterns
    properties: Dict[str, Any] = field(default_factory=dict)

class SimpleBinding:
    """
    Represents a simplified adhesive connection between models.
    
    Features:
    - Adhesive-based metaphor (tape, velcro, glue)
    - Two-state management (IDLE/ACTIVE)
    - Resource persistence
    """
    
    def __init__(self, config: SimpleBindingConfig):
        self.config = config
        self.created_at = datetime.now()
        self.last_used = None
        self.use_count = 0
        self._state = ResourceState.IDLE
        self._resource_pool: Dict[str, Any] = {}
    
    def use(self, pattern: Optional[InteractionPattern] = None) -> None:
        """Record binding usage"""
        # Validate pattern
        if pattern and pattern not in self.config.patterns:
            raise ValueError(f"Pattern {pattern} not allowed for this binding")
        
        self.last_used = datetime.now()
        self.use_count += 1
        self._state = ResourceState.ACTIVE
    
    def can_use(self, pattern: Optional[InteractionPattern] = None) -> bool:
        """Check if binding can be used"""
        if self._state == ResourceState.IDLE:
            return False
            
        if pattern and pattern not in self.config.patterns:
            return False
            
        return True
    
    def store_resource(self, key: str, data: Any) -> None:
        """Store resource data in binding"""
        if self.config.type == AdhesiveType.TAPE:
            # No persistence for tape
            return
            
        self._resource_pool[key] = data
    
    def get_resource(self, key: str) -> Optional[Any]:
        """Get stored resource data"""
        return self._resource_pool.get(key)
    
    def clear_resources(self) -> None:
        """Clear all stored resources"""
        self._resource_pool.clear()
    
    def get_state(self) -> ResourceState:
        """Get current binding state"""
        return self._state
    
    def destroy(self) -> None:
        """Destroy binding and cleanup resources"""
        self._state = ResourceState.IDLE
        self.clear_resources()
    
    def __str__(self) -> str:
        patterns = ", ".join(p.value for p in self.config.patterns)
        return (
            f"SimpleBinding({self.config.type.name}: "
            f"{self.config.source} -> {self.config.target}, "
            f"patterns=[{patterns}], "
            f"state={self._state.name})"
        )
