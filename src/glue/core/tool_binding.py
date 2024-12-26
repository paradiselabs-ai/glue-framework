"""Tool binding implementation for GLUE"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from .binding import AdhesiveType

@dataclass
class ToolBinding:
    """
    Configuration for binding tools to resources.
    
    Features:
    - Adhesive-based binding types (tape, velcro, glue, magnet)
    - Usage tracking
    - Context management
    - State persistence
    """
    type: AdhesiveType
    use_count: int = 0
    last_used: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def tape(cls, duration_ms: int = 1800000) -> 'ToolBinding':
        """Create a temporary tape binding"""
        return cls(
            type=AdhesiveType.TAPE,
            properties={"duration_ms": duration_ms}
        )
    
    @classmethod
    def velcro(cls, reconnect_attempts: int = 3) -> 'ToolBinding':
        """Create a swappable velcro binding"""
        return cls(
            type=AdhesiveType.VELCRO,
            properties={"reconnect_attempts": reconnect_attempts}
        )
    
    @classmethod
    def glue(cls, strength: float = 1.0) -> 'ToolBinding':
        """Create a permanent glue binding"""
        return cls(
            type=AdhesiveType.GLUE,
            properties={"strength": strength}
        )
    
    @classmethod
    def magnet(cls, polarity: str = "attract") -> 'ToolBinding':
        """Create a dynamic magnetic binding"""
        return cls(
            type=AdhesiveType.MAGNET,
            properties={"polarity": polarity}
        )
    
    def maintains_context(self) -> bool:
        """Check if binding maintains context between uses"""
        return self.type in {AdhesiveType.GLUE, AdhesiveType.MAGNET}
    
    def can_reconnect(self) -> bool:
        """Check if binding can reconnect after failure"""
        if self.type == AdhesiveType.VELCRO:
            max_attempts = self.properties.get("reconnect_attempts", 3)
            return self.use_count < max_attempts
        return False
    
    def should_break(self) -> bool:
        """Check if binding should break after use"""
        if self.type == AdhesiveType.TAPE:
            duration = self.properties.get("duration_ms", 1800000) / 1000  # convert to seconds
            if self.last_used:
                elapsed = datetime.now().timestamp() - self.last_used
                return elapsed > duration
        return False
