"""GLUE State Management System"""

import asyncio
from typing import Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from .resource import Resource, ResourceState

class TransitionError(Exception):
    """Error during state transition"""
    pass

@dataclass
class TransitionRule:
    """Rule for state transition"""
    from_states: Set[ResourceState]
    to_states: Set[ResourceState]
    validator: Optional[Callable[[Resource, ResourceState], bool]] = None
    side_effect: Optional[Callable[[Resource, ResourceState], None]] = None
    description: str = ""

@dataclass
class TransitionLog:
    """Log entry for state transition"""
    resource: str
    from_state: ResourceState
    to_state: ResourceState
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None

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
        self._history: Dict[str, List[TransitionLog]] = {}
        self._state_locks: Dict[str, asyncio.Lock] = {}
        
        # Setup default rules
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default transition rules"""
        # IDLE -> any state
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.IDLE},
                to_states={
                    ResourceState.ACTIVE,
                    ResourceState.LOCKED,
                    ResourceState.SHARED,
                    ResourceState.CHATTING,
                    ResourceState.PULLING
                },
                description="IDLE resources can transition to any state"
            )
        )
        
        # ACTIVE -> most states
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.ACTIVE},
                to_states={
                    ResourceState.IDLE,
                    ResourceState.LOCKED,
                    ResourceState.SHARED,
                    ResourceState.CHATTING
                },
                description="ACTIVE resources can transition to most states"
            )
        )
        
        # LOCKED -> IDLE only
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.LOCKED},
                to_states={ResourceState.IDLE},
                description="LOCKED resources can only return to IDLE"
            )
        )
        
        # SHARED -> non-exclusive states
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.SHARED},
                to_states={
                    ResourceState.IDLE,
                    ResourceState.ACTIVE,
                    ResourceState.SHARED,
                    ResourceState.CHATTING
                },
                description="SHARED resources can transition to non-exclusive states"
            )
        )
        
        # CHATTING -> communication states
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.CHATTING},
                to_states={
                    ResourceState.IDLE,
                    ResourceState.SHARED,
                    ResourceState.PULLING
                },
                description="CHATTING resources can transition to communication states"
            )
        )
        
        # PULLING -> limited states
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.PULLING},
                to_states={
                    ResourceState.IDLE,
                    ResourceState.CHATTING
                },
                description="PULLING resources have limited transitions"
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
        resource: Resource,
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
                # Validate transition
                if not await self.validate_transition(resource, new_state):
                    raise TransitionError(
                        f"Invalid transition: {resource.state} -> {new_state}"
                    )
                
                # Get transition rule
                rule = self._rules[resource.state][new_state]
                
                # Run custom validator if present
                if rule.validator:
                    if not rule.validator(resource, new_state):
                        raise TransitionError(
                            f"Transition validation failed: {resource.state} -> {new_state}"
                        )
                
                # Perform transition
                old_state = resource.state
                resource._state = new_state
                
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
    
    async def validate_transition(
        self,
        resource: Resource,
        new_state: ResourceState
    ) -> bool:
        """
        Validate if a transition is allowed
        
        Args:
            resource: Resource to check
            new_state: Target state
            
        Returns:
            bool: True if transition is valid
        """
        # Check if rule exists
        if (resource.state not in self._rules or
            new_state not in self._rules[resource.state]):
            return False
        
        return True
    
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
