"""Binding system for GLUE using adhesive metaphors"""

from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto

class AdhesiveType(Enum):
    """Types of adhesive bindings"""
    TAPE = auto()    # Temporary binding with no persistence
    VELCRO = auto()  # Flexible binding with partial persistence
    GLUE = auto()    # Permanent binding with full persistence

@dataclass
class BindingConfig:
    """Configuration for a binding between models"""
    type: AdhesiveType
    source: str  # source model name
    target: str  # target model name
    properties: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def tape(cls, source: str, target: str, duration: timedelta = timedelta(milliseconds=50)) -> 'BindingConfig':
        """Create a temporary tape binding"""
        return cls(
            type=AdhesiveType.TAPE,
            source=source,
            target=target,
            properties={"duration": duration}
        )
    
    @classmethod
    def velcro(cls, source: str, target: str, reconnect_attempts: int = 5) -> 'BindingConfig':
        """Create a swappable velcro binding"""
        return cls(
            type=AdhesiveType.VELCRO,
            source=source,
            target=target,
            properties={"reconnect_attempts": reconnect_attempts}
        )
    
    @classmethod
    def glue(cls, source: str, target: str, strength: float = 1.0) -> 'BindingConfig':
        """Create a permanent glue binding"""
        return cls(
            type=AdhesiveType.GLUE,
            source=source,
            target=target,
            properties={"strength": strength}
        )

class Binding:
    """
    Represents an adhesive connection between models.
    
    Features:
    - Adhesive-based metaphor (tape, velcro, glue)
    - Event handling
    - State tracking
    - Error propagation
    """
    
    def __init__(self, config: BindingConfig):
        self.config = config
        self.created_at = datetime.now()
        self.last_used = None
        self.use_count = 0
        self._active = True
        self._error_handlers: Dict[str, List[Callable]] = {}
        
        # Validate and setup based on type
        self._setup_binding()
    
    def _setup_binding(self) -> None:
        """Setup binding based on adhesive type"""
        if self.config.type == AdhesiveType.TAPE:
            if "duration" not in self.config.properties:
                self.config.properties["duration"] = timedelta(milliseconds=50)
                
        elif self.config.type == AdhesiveType.VELCRO:
            if "reconnect_attempts" not in self.config.properties:
                self.config.properties["reconnect_attempts"] = 5
                
        elif self.config.type == AdhesiveType.GLUE:
            if "strength" not in self.config.properties:
                self.config.properties["strength"] = 1.0
    
    def on(self, event: str, handler: Callable) -> None:
        """Register event handler"""
        if event not in self._error_handlers:
            self._error_handlers[event] = []
        self._error_handlers[event].append(handler)
    
    def _emit(self, event: str, data: Any = None) -> None:
        """Emit event to handlers"""
        if event in self._error_handlers:
            for handler in self._error_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Error in event handler: {e}")
    
    def use(self) -> None:
        """Record binding usage"""
        self.last_used = datetime.now()
        self.use_count += 1
        
        # Check tape binding expiration
        if self.config.type == AdhesiveType.TAPE:
            duration = self.config.properties["duration"]
            if isinstance(duration, timedelta):
                if (datetime.now() - self.created_at) > duration:
                    self.destroy()
                    self._emit("expired")
    
    def can_use(self) -> bool:
        """Check if binding can be used"""
        if not self._active:
            return False
            
        if self.config.type == AdhesiveType.TAPE:
            duration = self.config.properties["duration"]
            if isinstance(duration, timedelta):
                if (datetime.now() - self.created_at) > duration:
                    return False
                    
        elif self.config.type == AdhesiveType.VELCRO:
            # Velcro can be reattached if within reconnect attempts
            if self.use_count > self.config.properties["reconnect_attempts"]:
                return False
                
        return True
    
    def get_strength(self) -> float:
        """Get current binding strength with advanced degradation"""
        base_strength = self.config.properties.get("strength", 1.0)
        
        if self.config.type == AdhesiveType.TAPE:
            # Tape weakens over time
            duration = self.config.properties["duration"]
            if isinstance(duration, timedelta):
                elapsed = datetime.now() - self.created_at
                remaining = max(0, (duration - elapsed).total_seconds())
                return base_strength * (remaining / duration.total_seconds())
                
        elif self.config.type == AdhesiveType.VELCRO:
            # Velcro weakens with each use
            uses = self.use_count
            max_uses = self.config.properties["reconnect_attempts"]
            return base_strength * (1 - (uses / max_uses))
            
        return base_strength
    
    def destroy(self) -> None:
        """Destroy binding and cleanup resources"""
        self._active = False
        self._emit("destroyed")
        self._error_handlers.clear()
    
    def __str__(self) -> str:
        return (
            f"Binding({self.config.type.name}: "
            f"{self.config.source} -> {self.config.target}, "
            f"strength={self.get_strength():.2f}, "
            f"active={self._active})"
        )
