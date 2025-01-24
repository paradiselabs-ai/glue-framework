"""GLUE State Management System

Simplified state manager that only tracks IDLE/ACTIVE states and logs transitions.
Magnetic flow and adhesive persistence are handled separately by MagneticField
and AdhesiveManager respectively.
"""

import asyncio
from typing import Dict, Optional, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

from .types import ResourceState, TransitionLog

if TYPE_CHECKING:
    from .resource import Resource

class TransitionError(Exception):
    """Error during state transition"""
    pass

@dataclass
class StateContext:
    """Context for state transitions"""
    timestamp: datetime = datetime.now()
    metadata: Dict[str, Any] = None

class StateManager:
    """
    Simplified state manager following Anthropic's guidelines.
    
    Features:
    - Two states: IDLE and ACTIVE
    - Simple transitions
    - Transition logging
    - Thread-safe state changes
    """
    
    def __init__(self):
        """Initialize state manager"""
        self._states: Dict[str, ResourceState] = {}
        self._contexts: Dict[str, StateContext] = {}
        self._history: Dict[str, List[TransitionLog]] = {}
        self._state_locks: Dict[str, asyncio.Lock] = {}
    
    async def get_state(self, resource_name: str) -> ResourceState:
        """Get current state of a resource"""
        return self._states.get(resource_name, ResourceState.IDLE)
    
    async def set_state(
        self,
        resource_name: str,
        state: ResourceState,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Set resource state with optional context"""
        self._states[resource_name] = state
        if context:
            self._contexts[resource_name] = StateContext(metadata=context)
        return True
    
    async def transition_to_active(self, resource_name: str) -> bool:
        """Transition to ACTIVE state"""
        return await self.transition(resource_name, ResourceState.ACTIVE)
    
    async def transition_to_idle(self, resource_name: str) -> bool:
        """Transition to IDLE state"""
        return await self.transition(resource_name, ResourceState.IDLE)
    
    async def transition(
        self,
        resource_name: str,
        new_state: ResourceState,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition a resource to a new state
        
        Args:
            resource_name: Name of resource to transition
            new_state: Target state
            context: Optional context metadata
            
        Returns:
            bool: True if transition successful
        """
        # Get or create resource lock
        if resource_name not in self._state_locks:
            self._state_locks[resource_name] = asyncio.Lock()
        
        async with self._state_locks[resource_name]:
            try:
                # Get current state
                old_state = await self.get_state(resource_name)
                
                # Set new state
                await self.set_state(resource_name, new_state, context)
                
                # Log successful transition
                self._log_transition(
                    TransitionLog(
                        resource=resource_name,
                        from_state=old_state,
                        to_state=new_state
                    )
                )
                
                return True
                
            except Exception as e:
                # Log failed transition
                self._log_transition(
                    TransitionLog(
                        resource=resource_name,
                        from_state=old_state,
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
        active = sum(1 for state in self._states.values() if state == ResourceState.ACTIVE)
        total = len(self._states)
        return f"StateManager({active} active, {total} total)"
