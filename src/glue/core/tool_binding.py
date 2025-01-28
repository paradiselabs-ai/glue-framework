"""Tool Binding System


Provides natural binding types (TAPE/VELCRO/GLUE) with clear semantics:

- TAPE: Temporary, single-use bindings
- VELCRO: Session-level persistence with reconnection
- GLUE: Permanent team-level persistence

Example Usage:
```python
# Temporary binding
binding = ToolBinding.tape()
result = await tool.execute(binding)  # Binding breaks after use

# Session binding
binding = ToolBinding.velcro()
result1 = await tool.execute(binding)
result2 = await tool.execute(binding)  # Same binding persists

# Permanent binding
binding = ToolBinding.glue()
team.add_tool(tool, binding)  # Tool persists at team level
```
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from .types import AdhesiveType, ResourceState

@dataclass
class ToolBinding:
    """
    Configuration for binding tools to resources.
    
    Features:
    - Natural state management (IDLE/ACTIVE)
    - Intuitive adhesive types with clear semantics:
        * TAPE: Single-use, temporary bindings that break after use
        * VELCRO: Session-level persistence with limited reconnection attempts
        * GLUE: Permanent team-level persistence with full state management
    - Smart resource handling based on binding type
    
    Edge Cases:
    - TAPE bindings break immediately after use, even if duration hasn't expired
    - VELCRO bindings track reconnection attempts and weaken with each use
    - GLUE bindings delegate resource storage to team level for persistence
    
    State Transitions:
    - IDLE -> ACTIVE: Through bind() method, fails if already active
    - ACTIVE -> IDLE: Through unbind() or automatic breaking conditions
    - Breaking conditions:
        * TAPE: After first use or duration expiry
        * VELCRO: After max reconnection attempts
        * GLUE: Only through explicit unbind()
    """
    type: AdhesiveType
    use_count: int = 0
    last_used: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    state: ResourceState = ResourceState.IDLE
    resource_pool: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def tape(cls, duration_ms: int = 1800000) -> 'ToolBinding':
        """Create a temporary tape binding with no persistence"""
        return cls(
            type=AdhesiveType.TAPE,
            properties={
                "duration_ms": duration_ms,
                "maintains_context": False
            }
        )
    
    @classmethod
    def velcro(cls, reconnect_attempts: int = 3) -> 'ToolBinding':
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
    def glue(cls, strength: float = 1.0) -> 'ToolBinding':
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
        """Check if binding should break after use.
        
        Breaking conditions by type:
        - TAPE: Always breaks after first use
        - VELCRO: Breaks after max reconnection attempts
        - GLUE: Never breaks from use
        
        Returns:
            bool: True if binding should break, False otherwise
        """
        if self.state == ResourceState.IDLE:
            return True
            
        if self.type == AdhesiveType.TAPE:
            # TAPE breaks immediately after any use
            return self.use_count > 0
            
        if self.type == AdhesiveType.VELCRO:
            # VELCRO breaks after max reconnection attempts
            max_attempts = self.properties.get("reconnect_attempts", 3)
            return self.use_count >= max_attempts
            
        # GLUE never breaks from use
        return False
    
    def store_resource(self, key: str, data: Any) -> None:
        """Store resource data in binding based on adhesive type.
        
        Args:
            key: Resource identifier
            data: Resource data to store
            
        Behavior by type:
            - TAPE: No storage (temporary use only)
            - VELCRO: Stored in session resource pool
            - GLUE: Delegated to team level storage (see team.py)
            
        Example:
            ```python
            # VELCRO binding stores for session
            binding = ToolBinding.velcro()
            binding.store_resource("result", calculation_result)
            
            # Later in same session
            result = binding.get_resource("result")
            
            # GLUE resources are handled by Team class:
            # await team.share_result(tool_name, result, AdhesiveType.GLUE)
            ```
        """
        if self.type == AdhesiveType.TAPE:
            return  # No persistence for TAPE
        elif self.type == AdhesiveType.VELCRO:
            self.resource_pool[key] = data
        # GLUE resources handled by Team.share_result()
    
    def get_resource(self, key: str) -> Optional[Any]:
        """Retrieve stored resource data based on adhesive type.
        
        Args:
            key: Resource identifier to retrieve
            
        Returns:
            Resource data if found, None otherwise
            
        Behavior by type:
            - TAPE: Always returns None (no storage)
            - VELCRO: Returns from session resource pool
            - GLUE: Returns None (handled at team level)
        """
        if self.type == AdhesiveType.VELCRO:
            return self.resource_pool.get(key)
        return None
    
    def clear_resources(self) -> None:
        """Clear all stored resources from the binding.
        
        This primarily affects VELCRO bindings, as:
        - TAPE bindings don't store resources
        - GLUE resources are managed at team level
        """
        self.resource_pool.clear()
    
    def use(self) -> None:
        """Record binding usage and update state.
        
        This method:
        1. Increments use count
        2. Updates last used timestamp
        3. Checks breaking conditions
        4. Updates state if broken
        5. Clears resources if state changes to IDLE
        
        Breaking conditions:
        - TAPE: Breaks after first use
        - VELCRO: Breaks after max reconnection attempts
        - GLUE: Never breaks from use
        """
        self.use_count += 1
        self.last_used = datetime.now().timestamp()
        
        if self.should_break():
            self.state = ResourceState.IDLE
            self.clear_resources()
    
    def bind(self) -> None:
        """Initialize binding and transition to ACTIVE state.
        
        This method:
        1. Verifies binding is in IDLE state
        2. Transitions to ACTIVE state
        
        Raises:
            ValueError: If binding is already initialized (not in IDLE state)
            
        Example:
            ```python
            binding = ToolBinding.velcro()
            binding.bind()  # Activates the binding
            try:
                binding.bind()  # Raises ValueError
            except ValueError as e:
                print("Cannot bind an active binding")
            ```
        """
        if self.state != ResourceState.IDLE:
            raise ValueError(
                f"Cannot bind: binding already initialized in state {self.state.name}"
            )
            
        self.state = ResourceState.ACTIVE
    
    def unbind(self) -> None:
        """Clean up binding and transition to IDLE state.
        
        This method:
        1. Clears any stored resources
        2. Transitions to IDLE state
        
        Behavior by type:
        - TAPE: Clears minimal temporary state
        - VELCRO: Clears session resource pool
        - GLUE: Only changes state (team resources persist)
        
        Note: This is safe to call multiple times and in any state.
        """
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
            f"ToolBinding({self.type.name}: "
            f"strength={self.get_strength():.2f}, "
            f"state={self.state.name})"
        )
