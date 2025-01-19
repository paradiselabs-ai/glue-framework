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
            app = GlueApp(name)
            try:
                return await func(app, *args, **kwargs)
            finally:
                await app.cleanup()
        return wrapper
    return decorator

def team(
    name: str,
    lead: Optional[Model] = None,
    members: Optional[List[Model]] = None,
    tools: Optional[List[BaseTool]] = None,
    sticky: bool = False
):
    """Create a team with models and tools"""
    def decorator(func):
        @wraps(func)
        async def wrapper(app: GlueApp, *args, **kwargs):
            # Create field
            field = app.add_field(
                name=name,
                lead=lead,
                members=members,
                tools=tools
            )
            # Apply sticky persistence if needed
            if sticky:
                for tool in (tools or []):
                    tool.sticky = True
            return await func(field, *args, **kwargs)
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
    - Team management
    - Tool distribution
    
    Example:
        ```python
        async with field("research") as f:
            # Add team lead
            await f.add_resource(researcher, is_lead=True)
            
            # Add team members
            await f.add_resource(assistant)
            
            # Add team tools
            await f.add_resource(web_search)
            await f.add_resource(file_handler)
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

def flow(source: str, target: str, type: str = "->"):
    """
    Define flow between teams
    
    Flow types:
    -> : Push resources (one-way)
    <-> : Full attraction (two-way)
    <> : Repel (prevent interaction)
    <- pull : Enable pull fallback
    
    Example:
        ```python
        @flow("research", "docs", "->")  # Research pushes to docs
        @flow("docs", "<- pull")         # Docs can pull if needed
        async def research_flow(app):
            # Flow is configured
            pass
        ```
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(app: GlueApp, *args, **kwargs):
            source_field = app.get_field(source)
            target_field = app.get_field(target)
            
            if type == "->":  # Push
                await source_field.enable_push(target_field)
            elif type == "<->":  # Full attraction
                await source_field.enable_chat(target_field)
            elif type == "<>":  # Repel
                await source_field.repel(target_field)
            elif type == "<- pull":  # Pull fallback
                await target_field.enable_pull(source_field)
                
            return await func(app, *args, **kwargs)
        return wrapper
    return decorator
