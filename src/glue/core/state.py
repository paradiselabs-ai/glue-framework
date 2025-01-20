"""GLUE State Management System"""

import asyncio
from typing import Dict, Set, Optional, Callable, Any, TYPE_CHECKING, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .types import ResourceState, TransitionLog, AdhesiveType
from .context import ContextState, InteractionType

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
    
    async def validate_flow(
        self,
        resource: 'Resource',
        new_state: ResourceState,
        context: Optional['ContextState'] = None
    ) -> bool:
        """Validate state transition based on magnetic flow rules"""
        current_state = resource.state
        
        # Check if transition is registered
        if (current_state, new_state) not in self._transitions:
            return False
            
        # Get rule and validate
        rule = self._rules.get(current_state, {}).get(new_state)
        if rule and rule.validator and not rule.validator(resource, new_state):
            return False
            
        # Check context-based flow restrictions
        if context and hasattr(context, 'interaction_type'):
            # Define valid states for each interaction
            valid_states = {
                InteractionType.CHAT: {
                    ResourceState.IDLE, 
                    ResourceState.CHATTING
                },
                InteractionType.RESEARCH: {
                    ResourceState.IDLE,
                    ResourceState.ACTIVE,
                    ResourceState.SHARED,
                    ResourceState.PULLING
                },
                InteractionType.TASK: None  # None means allow all states
            }
            
            # Get valid states for this interaction type
            allowed_states = valid_states.get(context.interaction_type)
            
            # If states are restricted and new state isn't allowed, reject
            if allowed_states is not None and new_state not in allowed_states:
                return False
        
        return True
        
    async def validate_persistence(
        self,
        resource: 'Resource',
        new_state: ResourceState
    ) -> bool:
        """Validate state transition based on adhesive binding rules"""
        if not hasattr(resource, 'binding_type'):
            return True
            
        current_state = resource.state
        binding = resource.binding_type
        
        # Define valid transitions for each binding type
        binding_rules = {
            AdhesiveType.GLUE: None,  # None means allow all transitions
            AdhesiveType.VELCRO: {
                ResourceState.IDLE: {ResourceState.SHARED},
                ResourceState.SHARED: {ResourceState.IDLE},
                ResourceState.PULLING: {ResourceState.IDLE}
            },
            AdhesiveType.TAPE: {
                ResourceState.IDLE: {ResourceState.SHARED},
                ResourceState.SHARED: {ResourceState.IDLE}
            }
        }
        
        # Get allowed transitions for this binding
        allowed_transitions = binding_rules.get(binding)
        
        # If no restrictions, allow transition
        if allowed_transitions is None:
            return True
            
        # Check if transition is allowed for this binding
        allowed_states = allowed_transitions.get(current_state, set())
        return new_state in allowed_states
        
    async def validate_transition(
        self,
        resource: 'Resource',
        new_state: ResourceState,
        context: Optional['ContextState'] = None
    ) -> bool:
        """Validate state transition with separated concerns"""
        # First check magnetic flow rules
        if not await self.validate_flow(resource, new_state, context):
            return False
            
        # Then check persistence rules
        if not await self.validate_persistence(resource, new_state):
            return False
            
        return True
    
    def add_transition(
        self,
        from_state: ResourceState,
        to_state: ResourceState,
        cleanup: Optional[Callable] = None,
        validator: Optional[Callable] = None,
        description: str = ""
    ) -> None:
        """Register valid state transition with optional validation"""
        # Register transition
        self._transitions[(from_state, to_state)] = True
        
        # Create rule if validator provided
        if validator:
            rule = TransitionRule(
                from_states={from_state},
                to_states={to_state},
                validator=validator,
                side_effect=cleanup,
                description=description
            )
            if from_state not in self._rules:
                self._rules[from_state] = {}
            self._rules[from_state][to_state] = rule
        # Otherwise just store cleanup
        elif cleanup:
            if from_state not in self._rules:
                self._rules[from_state] = {}
            self._rules[from_state][to_state] = TransitionRule(
                from_states={from_state},
                to_states={to_state},
                side_effect=cleanup,
                description=description
            )
    
    def _setup_default_rules(self) -> None:
        """Setup default transition rules"""
        # Define valid states for each interaction type
        interaction_states = {
            InteractionType.CHAT: {
                ResourceState.IDLE,
                ResourceState.CHATTING
            },
            InteractionType.RESEARCH: {
                ResourceState.IDLE,
                ResourceState.ACTIVE,
                ResourceState.SHARED,
                ResourceState.PULLING
            },
            InteractionType.TASK: {
                ResourceState.IDLE,
                ResourceState.ACTIVE,
                ResourceState.SHARED,
                ResourceState.CHATTING,
                ResourceState.PULLING
            }
        }
        
        # Add context-aware validation
        def validate_with_context(resource: 'Resource', new_state: ResourceState) -> bool:
            if hasattr(resource, '_context') and resource._context:
                valid_states = interaction_states.get(
                    resource._context.interaction_type,
                    {ResourceState.IDLE}  # Default to IDLE only
                )
                return new_state in valid_states
            return True  # No context restrictions
        
        # IDLE -> context-dependent states
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.IDLE},
                to_states=set.union(*interaction_states.values()),
                validator=validate_with_context,
                description="IDLE resources can transition based on context"
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
        
        # ACTIVE -> SHARED or CHATTING (with context validation)
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.ACTIVE},
                to_states={ResourceState.SHARED, ResourceState.CHATTING},
                validator=validate_with_context,
                description="ACTIVE resources can transition to SHARED or CHATTING"
            )
        )
        
        # SHARED -> ACTIVE or CHATTING (with context validation)
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.SHARED},
                to_states={ResourceState.ACTIVE, ResourceState.CHATTING},
                validator=validate_with_context,
                description="SHARED resources can transition to ACTIVE or CHATTING"
            )
        )
        
        # CHATTING -> PULLING (with context validation)
        self.add_rule(
            TransitionRule(
                from_states={ResourceState.CHATTING},
                to_states={ResourceState.PULLING},
                validator=validate_with_context,
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
