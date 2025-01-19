# src/glue/core/adhesive.py
from typing import Any, Optional, Dict, Set
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from .patterns import InteractionPattern

class AdhesiveType(Enum):
    """Types of bindings available"""
    GLUE = "glue"     # Permanent binding with full persistence
    VELCRO = "velcro" # Flexible binding with partial persistence
    TAPE = "tape"     # Temporary binding with no persistence

class AdhesiveState(Enum):
    """States an adhesive can be in"""
    INACTIVE = auto()  # Not yet activated
    ACTIVE = auto()    # Ready for use
    DEGRADED = auto()  # Weakened but usable
    EXPIRED = auto()   # No longer usable

@dataclass
class AdhesiveProperties:
    """Properties of an adhesive binding"""
    strength: float  # 0.0 to 1.0
    durability: float  # 0.0 to 1.0
    flexibility: float  # 0.0 to 1.0
    duration: Optional[timedelta] = None  # For temporary bindings
    is_reusable: bool = False
    max_uses: Optional[int] = None
    allowed_patterns: Set[InteractionPattern] = field(default_factory=set)
    resource_pool: Dict[str, Any] = field(default_factory=dict)

class Adhesive:
    """
    Base class for all binding types
    
    Features:
    - Interaction pattern support (><, ->, <-, <>)
    - State management and transitions
    - Resource persistence and pooling
    - Advanced degradation handling
    """
    def __init__(
        self,
        adhesive_type: AdhesiveType,
        current_time: Optional[datetime] = None,
        patterns: Optional[Set[InteractionPattern]] = None
    ):
        self.type = adhesive_type
        self.properties = self._get_default_properties(patterns)
        self.created_at = current_time or datetime.now()
        self.uses = 0
        self.state = AdhesiveState.INACTIVE
        self._current_time = current_time

    def _get_default_properties(
        self,
        patterns: Optional[Set[InteractionPattern]] = None
    ) -> AdhesiveProperties:
        """Get default properties for this adhesive type"""
        defaults = {
            AdhesiveType.GLUE: AdhesiveProperties(
                strength=1.0,  # Full persistence
                durability=1.0,
                flexibility=0.3,
                is_reusable=False,
                max_uses=None,  # Unlimited uses
                allowed_patterns={InteractionPattern.ATTRACT}  # Only attraction
            ),
            AdhesiveType.VELCRO: AdhesiveProperties(
                strength=0.7,  # Partial persistence
                durability=0.8,
                flexibility=0.8,
                is_reusable=True,
                max_uses=5,  # Limited reusability
                allowed_patterns={  # Multiple patterns
                    InteractionPattern.ATTRACT,
                    InteractionPattern.PUSH,
                    InteractionPattern.PULL
                }
            ),
            AdhesiveType.TAPE: AdhesiveProperties(
                strength=0.3,  # No persistence
                durability=0.4,
                flexibility=0.9,
                duration=timedelta(milliseconds=50),
                is_reusable=False,
                max_uses=1,  # Single use
                allowed_patterns={InteractionPattern.ATTRACT}  # Only attraction
            )
        }
        
        props = defaults[self.type]
        if patterns:
            props.allowed_patterns = patterns
        return props

    def activate(self) -> None:
        """Activate the adhesive"""
        if self.state != AdhesiveState.INACTIVE:
            raise ValueError("Adhesive already activated")
            
        self.state = AdhesiveState.ACTIVE

    def can_bind(self, pattern: Optional[InteractionPattern] = None) -> bool:
        """
        Check if this adhesive can still create bindings
        
        Args:
            pattern: Optional interaction pattern to check
        """
        if self.state in [AdhesiveState.INACTIVE, AdhesiveState.EXPIRED]:
            return False
            
        if pattern and pattern not in self.properties.allowed_patterns:
            return False
            
        if self.properties.duration:
            current_time = self._current_time or datetime.now()
            if current_time - self.created_at > self.properties.duration:
                self.state = AdhesiveState.EXPIRED
                return False
                
        if self.properties.max_uses:
            if self.uses >= self.properties.max_uses:
                self.state = AdhesiveState.EXPIRED
                return False
                
        return True

    def use(self, pattern: Optional[InteractionPattern] = None) -> bool:
        """
        Use this adhesive for a binding
        
        Args:
            pattern: Optional interaction pattern being used
        """
        if not self.can_bind(pattern):
            return False
            
        self.uses += 1
        
        # Check for degradation
        strength = self.get_strength()
        if strength < 0.5 and strength > 0:
            self.state = AdhesiveState.DEGRADED
            
        return True

    def get_strength(self) -> float:
        """Get current binding strength with advanced degradation"""
        if self.state == AdhesiveState.EXPIRED:
            return 0.0
            
        if self.state == AdhesiveState.INACTIVE:
            return 0.0
        
        base_strength = self.properties.strength
        
        # Strength degrades for temporary bindings
        if self.properties.duration:
            current_time = self._current_time or datetime.now()
            elapsed = current_time - self.created_at
            remaining_ratio = 1 - (elapsed / self.properties.duration)
            return base_strength * max(0, remaining_ratio)
        
        # Strength degrades with uses for reusable bindings
        if self.properties.is_reusable and self.properties.max_uses:
            uses_ratio = 1 - (self.uses / self.properties.max_uses)
            return base_strength * max(0, uses_ratio)
        
        return base_strength
    
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
            
        self.properties.resource_pool[key] = data
    
    def get_resource(self, key: str) -> Optional[Any]:
        """
        Get stored resource data
        
        Args:
            key: Resource identifier
        """
        return self.properties.resource_pool.get(key)
    
    def clear_resources(self) -> None:
        """Clear all stored resources"""
        self.properties.resource_pool.clear()

class AdhesiveFactory:
    """Factory for creating adhesive instances"""
    @staticmethod
    def create(
        adhesive_type: str,
        patterns: Optional[Set[InteractionPattern]] = None,
        current_time: Optional[datetime] = None
    ) -> Adhesive:
        """
        Create an adhesive of the specified type
        
        Args:
            adhesive_type: Type of adhesive to create
            patterns: Optional allowed interaction patterns
            current_time: Optional current time for testing
        """
        try:
            type_enum = AdhesiveType(adhesive_type)
            adhesive = Adhesive(type_enum, current_time, patterns)
            adhesive.activate()
            return adhesive
        except ValueError:
            raise ValueError(f"Unknown adhesive type: {adhesive_type}")

    @staticmethod
    def create_with_properties(
        adhesive_type: str,
        properties: AdhesiveProperties,
        current_time: Optional[datetime] = None
    ) -> Adhesive:
        """
        Create an adhesive with custom properties
        
        Args:
            adhesive_type: Type of adhesive to create
            properties: Custom properties
            current_time: Optional current time for testing
        """
        adhesive = AdhesiveFactory.create(adhesive_type, properties.allowed_patterns, current_time)
        adhesive.properties = properties
        return adhesive
