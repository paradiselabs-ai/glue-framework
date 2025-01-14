"""GLUE State Management System"""

import asyncio
from typing import Dict, Set, Optional, Callable, Any, TYPE_CHECKING, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .types import ResourceState, TransitionLog, AdhesiveType

if TYPE_CHECKING:
    from .resource import Resource

class TransitionError(Exception):
    """Error during state transition"""
    pass

@dataclass
class TransitionRule:
    """Rule for state transition"""
    from_states: Set[ResourceState]
    to_states: Set[ResourceState]
    validator: Optional[Callable[['Resource', ResourceState], bool]] = None
    side_effect: Optional[Callable[['Resource', ResourceState], None]] = None
    description: str = ""

class StateManager:
    """
    Manages state transitions for resources.
    
    Features:
    - Validates transitions using rules
    - Handles transition side effects
    - Maintains transition history
    - Provides state consistency
    """
    
    def __init__(self):
        """Initialize state manager"""
        self._rules: Dict[ResourceState, Dict[ResourceState, TransitionRule]] = {}
        self._transitions: Dict[Tuple[ResourceState, ResourceState], bool] = {}
        self._history: Dict[str, List[TransitionLog]] = {}
        self._state_locks: Dict[str, asyncio.Lock] = {}
        
        # Setup default rules
        self._setup_default_rules()
    
    async def validate_transition(
        self,
        resource: 'Resource',
        new_state: ResourceState
    ) -> bool:
        # First check registered transitions
        if (resource.state, new_state) not in self._transitions:
            return False
        
        # Check if resource is locked
        if resource.state == ResourceState.LOCKED:
            return new_state == ResourceState.IDLE
            
        # Handle special cases for SHARED state
        if new_state == ResourceState.SHARED:
            # Only allow transition to SHARED from IDLE or ACTIVE
            if resource.state not in {ResourceState.IDLE, ResourceState.ACTIVE}:
                return False
            # Ensure resource is not already SHARED
            if resource.state == ResourceState.SHARED:
                return False
            
        # Handle binding type specific rules
        if hasattr(resource, 'binding_type'):
            # GLUE bindings allow transitions based on state rules
            if resource.binding_type == AdhesiveType.GLUE:
                return (resource.state, new_state) in self._transitions
            # VELCRO allows reconnection
            if resource.binding_type == AdhesiveType.VELCRO:
                return new_state in [ResourceState.IDLE, ResourceState.SHARED]
            # TAPE only allows one transition to SHARED then IDLE
            if resource.binding_type == AdhesiveType.TAPE:
                if resource.state == ResourceState.IDLE:
                    return new_state == ResourceState.SHARED
                if resource.state == ResourceState.SHARED:
                    return new_state == ResourceState.IDLE
            
        # Default to transition rules
        return (resource.state, new_state) in self._transitions
    
    def add_transition(
        self,
        from_state: ResourceState,
        to_state: ResourceState,
        cleanup: Optional[Callable] = None
    ) -> None:
        """Register valid state transition"""
        self._transitions[(from_state, to_state)] = True
    
    def _setup_default_rules(self) -> None:
        """Setup default transition rules"""
        # IDLE -> ACTIVE/SHARED
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.IDLE},
                to_states={
                    ResourceState.ACTIVE,
                    ResourceState.SHARED
                },
                description="IDLE resources can transition to ACTIVE or SHARED"
            )
        )
        
        # All states can return to IDLE
        for state in ResourceState:
            if state != ResourceState.IDLE:
                self.add_rule(
                    TransitionRule(
                        from_states={state},
                        to_states={ResourceState.IDLE},
                        description=f"{state.name} can return to IDLE"
                    )
                )
        
        # ACTIVE -> SHARED or CHATTING
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.ACTIVE},
                to_states={ResourceState.SHARED, ResourceState.CHATTING},
                description="ACTIVE resources can transition to SHARED or CHATTING"
            )
        )
        
        # SHARED -> ACTIVE, CHATTING or IDLE
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.SHARED},
                to_states={ResourceState.ACTIVE, ResourceState.CHATTING, ResourceState.IDLE},
                description="SHARED resources can transition to ACTIVE, CHATTING or IDLE"
            )
        )
        
        # CHATTING -> PULLING
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.CHATTING},
                to_states={ResourceState.PULLING},
                description="CHATTING resources can transition to PULLING"
            )
        )
    
    def add_rule(self, rule: TransitionRule) -> None:
        """Add a transition rule"""
        for from_state in rule.from_states:
            if from_state not in self._rules:
                self._rules[from_state] = {}
            for to_state in rule.to_states:
                self._rules[from_state][to_state] = rule
    
    async def transition(
        self,
        resource: 'Resource',
        new_state: ResourceState,
        context: Optional['ContextState'] = None
    ) -> bool:
        """
        Transition a resource to a new state
        
        Args:
            resource: Resource to transition
            new_state: Target state
            context: Optional context for validation
            
        Returns:
            bool: True if transition successful
            
        Raises:
            TransitionError: If transition is invalid
        """
        # Get or create resource lock
        if resource.name not in self._state_locks:
            self._state_locks[resource.name] = asyncio.Lock()
        
        async with self._state_locks[resource.name]:
            try:
                # Check if resource is locked
                if resource.state == ResourceState.LOCKED and new_state != ResourceState.IDLE:
                    raise TransitionError(
                        f"Cannot transition from LOCKED to {new_state}"
                    )
                
                # Validate transition
                if not await self.validate_transition(resource, new_state):
                    raise TransitionError(
                        f"Invalid transition: {resource.state} -> {new_state}"
                    )
                
                # Check if resource is already in target state
                if resource.state == new_state:
                    return True
                
                # Get transition rule
                rule = self._rules[resource.state][new_state]
                
                # Run custom validator if present
                if rule.validator:
                    if not rule.validator(resource, new_state):
                        raise TransitionError(
                            f"Transition validation failed: {resource.state} -> {new_state}"
                        )
                
                # Get current state and version
                old_state = resource.state
                current_version = resource._version
                
                # Attempt to set state with version check
                if not await resource.set_state(new_state, current_version):
                    return False
                
                # Run side effect if present
                if rule.side_effect:
                    rule.side_effect(resource, old_state)
                
                # Update context if provided
                if context:
                    await resource.update_context(context)
                
                # Log successful transition
                self._log_transition(
                    TransitionLog(
                        resource=resource.name,
                        from_state=old_state,
                        to_state=new_state
                    )
                )
                
                return True
                
            except Exception as e:
                # Log failed transition
                self._log_transition(
                    TransitionLog(
                        resource=resource.name,
                        from_state=resource.state,
                        to_state=new_state,
                        success=False,
                        error=str(e)
                    )
                )
                raise
    
    def _log_transition(self, log: TransitionLog) -> None:
        """Log a transition"""
        if log.resource not in self._history:
            self._history[log.resource] = []
        self._history[log.resource].append(log)
    
    def get_history(
        self,
        resource: Optional[str] = None,
        success_only: bool = False
    ) -> List[TransitionLog]:
        """
        Get transition history
        
        Args:
            resource: Optional resource name to filter by
            success_only: Only return successful transitions
            
        Returns:
            List of transition logs
        """
        if resource:
            logs = self._history.get(resource, [])
        else:
            logs = [log for logs in self._history.values() for log in logs]
        
        if success_only:
            logs = [log for log in logs if log.success]
        
        return sorted(logs, key=lambda x: x.timestamp)
    
    def clear_history(self, resource: Optional[str] = None) -> None:
        """
        Clear transition history
        
        Args:
            resource: Optional resource name to clear history for
        """
        if resource:
            self._history.pop(resource, None)
        else:
            self._history.clear()
    
    def __str__(self) -> str:
        """String representation"""
        return f"StateManager({len(self._rules)} rules, {len(self._history)} resources)"
