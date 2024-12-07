# src/glue/core/adhesive.py
from typing import Any, Optional, Dict
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

class AdhesiveType(Enum):
    """Types of bindings available"""
    GLUE = "glue"         # Permanent binding
    SUPER_GLUE = "super_glue"  # Immutable binding
    VELCRO = "velcro"     # Swappable binding
    TAPE = "tape"         # Temporary binding
    MAGNET = "magnet"     # Dynamic binding
    DUCT_TAPE = "duct_tape"  # Fallback binding

@dataclass
class AdhesiveProperties:
    """Properties of an adhesive binding"""
    strength: float  # 0.0 to 1.0
    durability: float  # 0.0 to 1.0
    flexibility: float  # 0.0 to 1.0
    duration: Optional[timedelta] = None  # For temporary bindings
    is_reusable: bool = False
    max_uses: Optional[int] = None

class Adhesive:
    """Base class for all binding types"""
    def __init__(self, adhesive_type: AdhesiveType, current_time: Optional[datetime] = None):
        self.type = adhesive_type
        self.properties = self._get_default_properties()
        self.created_at = current_time or datetime.now()
        self.uses = 0
        self.active = True
        self._current_time = current_time

    def _get_default_properties(self) -> AdhesiveProperties:
        """Get default properties for this adhesive type"""
        defaults = {
            AdhesiveType.GLUE: AdhesiveProperties(
                strength=0.8,
                durability=0.9,
                flexibility=0.3,
                is_reusable=False
            ),
            AdhesiveType.SUPER_GLUE: AdhesiveProperties(
                strength=1.0,
                durability=1.0,
                flexibility=0.0,
                is_reusable=False
            ),
            AdhesiveType.VELCRO: AdhesiveProperties(
                strength=0.6,
                durability=0.7,
                flexibility=0.8,
                is_reusable=True
            ),
            AdhesiveType.TAPE: AdhesiveProperties(
                strength=0.4,
                durability=0.3,
                flexibility=0.9,
                duration=timedelta(milliseconds=50),
                is_reusable=False
            ),
            AdhesiveType.MAGNET: AdhesiveProperties(
                strength=0.5,
                durability=1.0,
                flexibility=1.0,
                is_reusable=True
            ),
            AdhesiveType.DUCT_TAPE: AdhesiveProperties(
                strength=0.7,
                durability=0.5,
                flexibility=0.6,
                is_reusable=False
            )
        }
        return defaults[self.type]

    def can_bind(self) -> bool:
        """Check if this adhesive can still create bindings"""
        if not self.active:
            return False
            
        if self.properties.duration:
            current_time = self._current_time or datetime.now()
            if current_time - self.created_at > self.properties.duration:
                self.active = False
                return False
                
        if self.properties.max_uses:
            if self.uses >= self.properties.max_uses:
                self.active = False
                return False
                
        return True

    def use(self) -> bool:
        """Use this adhesive for a binding"""
        if not self.can_bind():
            return False
            
        self.uses += 1
        return True

    def get_strength(self) -> float:
        """Get current binding strength"""
        if not self.active:
            return 0.0
            
        base_strength = self.properties.strength
        
        # Strength degrades over time for temporary bindings
        if self.properties.duration:
            current_time = self._current_time or datetime.now()
            elapsed = current_time - self.created_at
            remaining_ratio = 1 - (elapsed / self.properties.duration)
            return base_strength * max(0, remaining_ratio)
            
        return base_strength

class AdhesiveFactory:
    """Factory for creating adhesive instances"""
    @staticmethod
    def create(adhesive_type: str, current_time: Optional[datetime] = None) -> Adhesive:
        """Create an adhesive of the specified type"""
        try:
            type_enum = AdhesiveType(adhesive_type)
            return Adhesive(type_enum, current_time)
        except ValueError:
            raise ValueError(f"Unknown adhesive type: {adhesive_type}")

    @staticmethod
    def create_with_properties(
        adhesive_type: str,
        properties: AdhesiveProperties,
        current_time: Optional[datetime] = None
    ) -> Adhesive:
        """Create an adhesive with custom properties"""
        adhesive = AdhesiveFactory.create(adhesive_type, current_time)
        adhesive.properties = properties
        return adhesive