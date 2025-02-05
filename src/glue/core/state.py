"""GLUE State Management System

Simplified state manager that only tracks IDLE/ACTIVE states.
Magnetic flow and adhesive persistence are handled separately by MagneticField
and AdhesiveManager respectively.
"""

import asyncio
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .types import ResourceState

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
    - Thread-safe state changes
    """
    
    def __init__(self):
        """Initialize state manager"""
        self._states: Dict[str, ResourceState] = {}
        self._contexts: Dict[str, StateContext] = {}
        self._state_locks: Dict[str, asyncio.Lock] = {}
    
    async def get_state(self, resource_name: str) -> ResourceState:
        """Get current state of a resource"""
        return self._states.get(resource_name, ResourceState.IDLE)
        
    def get_context(self) -> Dict[str, Any]:
        """Get current context for conversation"""
        # Initialize with empty context
        context = {
            "states": {},
            "metadata": {},
            "active_resources": []
        }
        
        # Add state information
        for resource_name, state in self._states.items():
            context["states"][resource_name] = state.name
            if state == ResourceState.ACTIVE:
                context["active_resources"].append(resource_name)
                if resource_name in self._contexts:
                    context["metadata"].update(self._contexts[resource_name].metadata or {})
        
        return context
    
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
            # Set new state
            await self.set_state(resource_name, new_state, context)
            return True
    
    def __str__(self) -> str:
        """String representation"""
        active = sum(1 for state in self._states.values() if state == ResourceState.ACTIVE)
        total = len(self._states)
        return f"StateManager({active} active, {total} total)"
