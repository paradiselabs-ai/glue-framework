# src/glue/core/simple_adhesive.py

"""Simplified Adhesive Implementation"""

from typing import Any, Optional, Dict, Set
from datetime import datetime, timedelta
from .types import AdhesiveType, ResourceState, InteractionPattern

class SimpleAdhesive:
    """
    Simplified adhesive binding system.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Basic resource persistence
    - Interaction pattern support
    """
    def __init__(
        self,
        adhesive_type: AdhesiveType,
        patterns: Optional[Set[InteractionPattern]] = None
    ):
        self.type = adhesive_type
        self.created_at = datetime.now()
        self.uses = 0
        self.state = ResourceState.IDLE
        self.patterns = patterns or {InteractionPattern.ATTRACT}
        
        # Properties based on type
        if adhesive_type == AdhesiveType.GLUE:
            self.strength = 1.0
            self.max_uses = None  # Unlimited
            self.duration = None  # Permanent
        elif adhesive_type == AdhesiveType.VELCRO:
            self.strength = 0.7
            self.max_uses = 5
            self.duration = None  # Session-based
        else:  # TAPE
            self.strength = 0.3
            self.max_uses = 1
            self.duration = timedelta(milliseconds=50)
        
        # Resource storage
        self._resources: Dict[str, Any] = {}

    def activate(self) -> None:
        """Activate the adhesive"""
        if self.state != ResourceState.IDLE:
            raise ValueError("Adhesive already activated")
        self.state = ResourceState.ACTIVE

    def can_bind(self, pattern: Optional[InteractionPattern] = None) -> bool:
        """Check if adhesive can create bindings"""
        if self.state == ResourceState.IDLE:
            return False
            
        if pattern and pattern not in self.patterns:
            return False
            
        if self.duration and datetime.now() - self.created_at > self.duration:
            self.state = ResourceState.IDLE
            return False
            
        if self.max_uses and self.uses >= self.max_uses:
            self.state = ResourceState.IDLE
            return False
            
        return True

    def use(self, pattern: Optional[InteractionPattern] = None) -> bool:
        """Use adhesive for binding"""
        if not self.can_bind(pattern):
            return False
            
        self.uses += 1
        
        # Check if should transition to IDLE
        if self.get_strength() <= 0:
            self.state = ResourceState.IDLE
            return False
            
        return True

    def get_strength(self) -> float:
        """Get current binding strength"""
        if self.state == ResourceState.IDLE:
            return 0.0
        
        base_strength = self.strength
        
        # Degrade based on time for TAPE
        if self.duration:
            elapsed = datetime.now() - self.created_at
            remaining_ratio = 1 - (elapsed / self.duration)
            return base_strength * max(0, remaining_ratio)
        
        # Degrade based on uses for VELCRO
        if self.max_uses:
            uses_ratio = 1 - (self.uses / self.max_uses)
            return base_strength * max(0, uses_ratio)
        
        return base_strength
    
    def store_resource(self, key: str, data: Any) -> None:
        """Store resource data"""
        if self.type == AdhesiveType.TAPE:
            return  # No persistence for TAPE
        self._resources[key] = data
    
    def get_resource(self, key: str) -> Optional[Any]:
        """Get stored resource data"""
        return self._resources.get(key)
    
    def clear_resources(self) -> None:
        """Clear all stored resources"""
        self._resources.clear()

class SimpleAdhesiveFactory:
    """Factory for creating simple adhesive instances"""
    @staticmethod
    def create(
        adhesive_type: str,
        patterns: Optional[Set[InteractionPattern]] = None
    ) -> SimpleAdhesive:
        """Create an adhesive of the specified type"""
        try:
            type_enum = AdhesiveType(adhesive_type)
            adhesive = SimpleAdhesive(type_enum, patterns)
            adhesive.activate()
            return adhesive
        except ValueError:
            raise ValueError(f"Unknown adhesive type: {adhesive_type}")
