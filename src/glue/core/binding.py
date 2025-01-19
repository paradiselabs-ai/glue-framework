"""Binding system for GLUE using adhesive metaphors"""

from typing import Dict, Any, Optional, Callable, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from ..magnetic.rules import InteractionPattern
from .types import AdhesiveType

from .types import BindingState

@dataclass
class BindingConfig:
    """Configuration for a binding between models"""
    type: AdhesiveType
    source: str  # source model name
    target: str  # target model name
    patterns: Set[InteractionPattern] = field(default_factory=set)  # Allowed interaction patterns
    properties: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def tape(
        cls,
        source: str,
        target: str,
        patterns: Optional[Set[InteractionPattern]] = None,
        duration: timedelta = timedelta(milliseconds=50)
    ) -> 'BindingConfig':
        """
        Create a temporary tape binding
        
        Args:
            source: Source model name
            target: Target model name
            patterns: Allowed interaction patterns
            duration: How long binding lasts
        """
        return cls(
            type=AdhesiveType.TAPE,
            source=source,
            target=target,
            patterns=patterns or {InteractionPattern.ATTRACT},
            properties={"duration": duration}
        )
    
    @classmethod
    def velcro(
        cls,
        source: str,
        target: str,
        patterns: Optional[Set[InteractionPattern]] = None,
        reconnect_attempts: int = 5
    ) -> 'BindingConfig':
        """
        Create a swappable velcro binding
        
        Args:
            source: Source model name
            target: Target model name
            patterns: Allowed interaction patterns
            reconnect_attempts: Max reconnection attempts
        """
        return cls(
            type=AdhesiveType.VELCRO,
            source=source,
            target=target,
            patterns=patterns or {InteractionPattern.ATTRACT, InteractionPattern.PUSH, InteractionPattern.PULL},
            properties={"reconnect_attempts": reconnect_attempts}
        )
    
    @classmethod
    def glue(
        cls,
        source: str,
        target: str,
        patterns: Optional[Set[InteractionPattern]] = None,
        strength: float = 1.0
    ) -> 'BindingConfig':
        """
        Create a permanent glue binding
        
        Args:
            source: Source model name
            target: Target model name
            patterns: Allowed interaction patterns
            strength: Initial binding strength
        """
        return cls(
            type=AdhesiveType.GLUE,
            source=source,
            target=target,
            patterns=patterns or {InteractionPattern.ATTRACT},
            properties={"strength": strength}
        )

class Binding:
    """
    Represents an adhesive connection between models.
    
    Features:
    - Adhesive-based metaphor (tape, velcro, glue)
    - Interaction pattern support (><, ->, <-, <>)
    - Resource persistence
    - State management
    - Event handling
    """
    
    def __init__(self, config: BindingConfig):
        self.config = config
        self.created_at = datetime.now()
        self.last_used = None
        self.use_count = 0
        self._state = BindingState.ACTIVE
        self._error_handlers: Dict[str, List[Callable]] = {}
        self._resource_pool: Dict[str, Any] = {}
        
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
        """
        Register event handler
        
        Args:
            event: Event name to handle
            handler: Callback function for event
        """
        if event not in self._error_handlers:
            self._error_handlers[event] = []
        if handler not in self._error_handlers[event]:
            self._error_handlers[event].append(handler)
    
    def _emit(self, event: str, data: Any = None) -> None:
        """Emit event to handlers"""
        if event in self._error_handlers:
            for handler in self._error_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Error in event handler: {e}")
    
    def use(self, pattern: Optional[InteractionPattern] = None) -> None:
        """
        Record binding usage
        
        Args:
            pattern: Interaction pattern being used
        """
        # Validate pattern
        if pattern and pattern not in self.config.patterns:
            raise ValueError(f"Pattern {pattern} not allowed for this binding")
        
        self.last_used = datetime.now()
        self.use_count += 1
        
        # Check binding state
        if self.config.type == AdhesiveType.TAPE:
            duration = self.config.properties["duration"]
            if isinstance(duration, timedelta):
                if (datetime.now() - self.created_at) > duration:
                    self._state = BindingState.FAILED
                    self.destroy()
                    self._emit("expired")
                    
        elif self.config.type == AdhesiveType.VELCRO:
            # Check degradation
            if self.get_strength() < 0.5:
                self._state = BindingState.DEGRADED
                self._emit("degraded")
    
    def can_use(self, pattern: Optional[InteractionPattern] = None) -> bool:
        """
        Check if binding can be used
        
        Args:
            pattern: Interaction pattern to check
        """
        if self._state == BindingState.FAILED:
            return False
            
        if pattern and pattern not in self.config.patterns:
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
    
    def store_resource(self, key: str, data: Any) -> None:
        """
        Store resource data in binding
        
        Args:
            key: Resource identifier
            data: Resource data
        """
        if self.config.type == AdhesiveType.TAPE:
            # No persistence for tape
            return
            
        self._resource_pool[key] = data
        self._emit("resource_stored", {"key": key, "data": data})
    
    def get_resource(self, key: str) -> Optional[Any]:
        """
        Get stored resource data
        
        Args:
            key: Resource identifier
        """
        return self._resource_pool.get(key)
    
    def clear_resources(self) -> None:
        """Clear all stored resources"""
        self._resource_pool.clear()
        self._emit("resources_cleared")
    
    def get_state(self) -> BindingState:
        """Get current binding state"""
        return self._state
    
    def destroy(self) -> None:
        """Destroy binding and cleanup resources"""
        self._state = BindingState.FAILED
        self.clear_resources()
        self._emit("destroyed")
        self._error_handlers.clear()
    
    def __str__(self) -> str:
        patterns = ", ".join(p.value for p in self.config.patterns)
        return (
            f"Binding({self.config.type.name}: "
            f"{self.config.source} -> {self.config.target}, "
            f"patterns=[{patterns}], "
            f"strength={self.get_strength():.2f}, "
            f"state={self._state.name})"
        )
