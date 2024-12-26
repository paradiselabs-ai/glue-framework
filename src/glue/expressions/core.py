"""Core GLUE Expression Language Components"""

from functools import wraps
from typing import Any, List, Dict, Union, Optional, Set
from .chain import Chain
from ..core.registry import ResourceRegistry
from ..magnetic.field import MagneticField

def glue_app(name: str):
    """Create GLUE application with minimal boilerplate"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class field:
    """
    Magnetic field context with registry integration.
    
    Features:
    - Resource tracking
    - Field operations
    - Rule validation
    - Event handling
    - Registry integration
    
    Example:
        ```python
        async with field("workspace") as f:
            await f.add_resource(tool1)
            await f.add_resource(tool2)
            await f.attract(tool1, tool2)
        ```
    """
    def __init__(self, name: str):
        self.name = name
        self.registry = ResourceRegistry()
        self._field: Optional[MagneticField] = None
    
    async def __aenter__(self) -> MagneticField:
        """Enter field context with registry"""
        self._field = MagneticField(self.name, self.registry)
        return self._field
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit field context and cleanup"""
        if self._field:
            await self._field.cleanup()
            self._field = None
    
    def __call__(self, *args, **kwargs):
        """Allow both context manager and decorator usage"""
        if len(args) == 1 and callable(args[0]):
            return self.decorate(args[0])
        return self
    
    def decorate(self, func):
        """Decorator form for even less boilerplate"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)
        return wrapper

def magnet(
    name: str,
    sticky: bool = False,
    shared_resources: Optional[List[str]] = None,
    tags: Optional[Set[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create magnetic component with resource integration.
    
    Features:
    - Resource system integration
    - Magnetic API compatibility
    - Tag-based capabilities
    - Resource sharing
    
    Args:
        name: Component name
        sticky: Whether component persists
        shared_resources: Resources to share
        tags: Additional capability tags
        **kwargs: Additional configuration
    
    Returns:
        Dict with magnetic configuration
    """
    # Start with basic magnetic config
    config = {
        "name": name,
        "magnetic": True,  # For Resource system
        "__magnet__": True  # For API compatibility
    }
    
    # Add magnetic capabilities
    if sticky:
        config["sticky"] = True
    if shared_resources:
        config["shared_resources"] = shared_resources
    
    # Add tags
    all_tags = {"magnetic"}  # Always magnetic
    if sticky:
        all_tags.add("sticky")
    if tags:
        all_tags.update(tags)
    config["tags"] = all_tags
    
    # Add any additional config
    config.update(kwargs)
    
    return config

def magnetize(
    tools: Union[List[str], Dict[str, Any]],
    shared_resources: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Make tools magnetic with resource integration.
    
    Features:
    - Resource system integration
    - Magnetic API compatibility
    - Shared resource configuration
    - Tag-based capabilities
    
    Args:
        tools: Tools to magnetize
        shared_resources: Resources to share between tools
    
    Returns:
        Dict mapping tool names to magnetic configurations
    """
    if isinstance(tools, list):
        return {
            t: magnet(
                t,
                shared_resources=shared_resources
            ) for t in tools
        }
    
    result = {}
    for k, v in tools.items():
        if isinstance(v, dict):
            # Merge existing config with magnet defaults
            config = v.copy()
            config["name"] = k
            if shared_resources and "shared_resources" not in config:
                config["shared_resources"] = shared_resources
            result[k] = magnet(**config)
        else:
            result[k] = magnet(
                k,
                shared_resources=shared_resources
            )
    return result
