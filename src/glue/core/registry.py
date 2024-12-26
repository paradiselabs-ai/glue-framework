"""GLUE Resource Registry System"""

import asyncio
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from .resource import Resource, ResourceState
from .state import StateManager

@dataclass
class RegistryEntry:
    """Entry in the resource registry"""
    resource: Resource
    category: str
    registered_at: datetime = field(default_factory=datetime.now)
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

class ResourceRegistry:
    """
    Central registry for all GLUE resources.
    
    Features:
    - Resource registration and lookup
    - Category management
    - Resource querying
    - Lifecycle tracking
    """
    
    def __init__(self, state_manager: Optional[StateManager] = None):
        """Initialize registry"""
        self._resources: Dict[str, RegistryEntry] = {}
        self._categories: Dict[str, Set[str]] = defaultdict(set)
        self._tags: Dict[str, Set[str]] = defaultdict(set)
        self._state_manager = state_manager or StateManager()
        self._registry_lock = asyncio.Lock()
        self._observers: Dict[str, List[Callable[[str, Any], None]]] = defaultdict(list)
    
    def register(
        self,
        resource: Resource,
        category: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a resource
        
        Args:
            resource: Resource to register
            category: Resource category
            metadata: Optional metadata
        """
        if resource.name in self._resources:
            raise ValueError(f"Resource {resource.name} already registered")
            
        entry = RegistryEntry(
            resource=resource,
            category=category,
            metadata=metadata or {}
        )
        
        self._resources[resource.name] = entry
        self._categories[category].add(resource.name)
        
        # Register tags
        for tag in resource.metadata.tags:
            self._tags[tag].add(resource.name)
            
        # Notify observers
        self._notify_observers("register", {
            "resource": resource.name,
            "category": category
        })
    
    def unregister(self, resource_name: str) -> None:
        """
        Unregister a resource
        
        Args:
            resource_name: Name of resource to unregister
        """
        if resource_name not in self._resources:
            return
            
        entry = self._resources[resource_name]
        
        # Remove from categories
        self._categories[entry.category].discard(resource_name)
        if not self._categories[entry.category]:
            del self._categories[entry.category]
            
        # Remove from tags
        for tag in entry.resource.metadata.tags:
            self._tags[tag].discard(resource_name)
            if not self._tags[tag]:
                del self._tags[tag]
                
        # Remove entry
        del self._resources[resource_name]
        
        # Notify observers
        self._notify_observers("unregister", {
            "resource": resource_name,
            "category": entry.category
        })
    
    def get_resource(
        self,
        name: str,
        category: Optional[str] = None
    ) -> Optional[Resource]:
        """
        Get a resource by name
        
        Args:
            name: Resource name
            category: Optional category to validate
            
        Returns:
            Resource if found, None otherwise
        """
        entry = self._resources.get(name)
        if not entry:
            return None
            
        if category and entry.category != category:
            return None
            
        # Update access metadata
        entry.last_accessed = datetime.now()
        entry.access_count += 1
        
        return entry.resource
    
    def get_resources_by_category(
        self,
        category: str
    ) -> List[Resource]:
        """
        Get all resources in a category
        
        Args:
            category: Category to filter by
            
        Returns:
            List of resources in category
        """
        resources = []
        for name in self._categories.get(category, set()):
            if resource := self.get_resource(name):
                resources.append(resource)
        return resources
    
    def get_resources_by_tag(
        self,
        tag: str
    ) -> List[Resource]:
        """
        Get all resources with a tag
        
        Args:
            tag: Tag to filter by
            
        Returns:
            List of resources with tag
        """
        resources = []
        for name in self._tags.get(tag, set()):
            if resource := self.get_resource(name):
                resources.append(resource)
        return resources
    
    def get_resources_by_state(
        self,
        state: ResourceState
    ) -> List[Resource]:
        """
        Get all resources in a state
        
        Args:
            state: State to filter by
            
        Returns:
            List of resources in state
        """
        return [
            entry.resource for entry in self._resources.values()
            if entry.resource.state == state
        ]
    
    def find_resources(
        self,
        category: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        state: Optional[ResourceState] = None
    ) -> List[Resource]:
        """
        Find resources matching criteria
        
        Args:
            category: Optional category filter
            tags: Optional tag filters (all must match)
            state: Optional state filter
            
        Returns:
            List of matching resources
        """
        resources = set(self._resources.keys())
        
        if category:
            resources &= self._categories.get(category, set())
            
        if tags:
            for tag in tags:
                resources &= self._tags.get(tag, set())
                
        matching = []
        for name in resources:
            resource = self.get_resource(name)
            if resource and (not state or resource.state == state):
                matching.append(resource)
                
        return matching
    
    async def transition_resource(
        self,
        resource_name: str,
        new_state: ResourceState,
        context: Optional['ContextState'] = None
    ) -> bool:
        """
        Transition a resource's state
        
        Args:
            resource_name: Resource to transition
            new_state: Target state
            context: Optional context
            
        Returns:
            bool: True if transition successful
        """
        resource = self.get_resource(resource_name)
        if not resource:
            return False
            
        async with self._registry_lock:
            success = await self._state_manager.transition(
                resource,
                new_state,
                context
            )
            
            if success:
                self._notify_observers("state_change", {
                    "resource": resource_name,
                    "old_state": resource.state,
                    "new_state": new_state
                })
            
            return success
    
    def add_observer(
        self,
        event_type: str,
        observer: Callable[[str, Any], None]
    ) -> None:
        """
        Add an observer for registry events
        
        Args:
            event_type: Type of event to observe
            observer: Callback function
        """
        self._observers[event_type].append(observer)
    
    def remove_observer(
        self,
        event_type: str,
        observer: Callable[[str, Any], None]
    ) -> None:
        """
        Remove an observer
        
        Args:
            event_type: Type of event
            observer: Observer to remove
        """
        if event_type in self._observers:
            self._observers[event_type].remove(observer)
            if not self._observers[event_type]:
                del self._observers[event_type]
    
    def _notify_observers(self, event_type: str, data: Any) -> None:
        """Notify observers of an event"""
        for observer in self._observers.get(event_type, []):
            try:
                observer(event_type, data)
            except Exception as e:
                print(f"Error in observer: {str(e)}")
    
    def get_categories(self) -> List[str]:
        """Get all registered categories"""
        return list(self._categories.keys())
    
    def get_tags(self) -> List[str]:
        """Get all registered tags"""
        return list(self._tags.keys())
    
    def get_resource_count(
        self,
        category: Optional[str] = None
    ) -> int:
        """
        Get number of registered resources
        
        Args:
            category: Optional category filter
            
        Returns:
            Number of resources
        """
        if category:
            return len(self._categories.get(category, set()))
        return len(self._resources)
    
    def clear(self) -> None:
        """Clear all registered resources"""
        self._resources.clear()
        self._categories.clear()
        self._tags.clear()
        self._notify_observers("clear", None)
    
    def __str__(self) -> str:
        """String representation"""
        return (
            f"ResourceRegistry("
            f"resources={len(self._resources)}, "
            f"categories={len(self._categories)}, "
            f"tags={len(self._tags)})"
        )
