# src/glue/adhesive/__init__.py

"""GLUE Adhesive System - Intuitive Tool Binding"""

import inspect
from enum import Enum
from typing import Any, List, Dict, Union, Optional, Callable
from functools import wraps
from ..tools import TOOL_TYPES

class AdhesiveType(Enum):
    """Types of adhesive bonds"""
    TAPE = "tape"          # Testing/development
    VELCRO = "velcro"      # Easily swappable
    DUCT_TAPE = "duct"     # Error handling
    GLUE = "glue"         # Standard development
    EPOXY = "epoxy"       # Permanent config
    SUPER_GLUE = "super"  # Production deployment

class Workspace:
    """Environment for tool interactions"""
    def __init__(self, name: str):
        self.name = name
        self.tools = {}
        self.bonds = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        # Cleanup workspace
        for tool in self.tools.values():
            if hasattr(tool, "cleanup"):
                await tool.cleanup()

def workspace(name: str) -> Workspace:
    """Create a workspace for tools"""
    return Workspace(name)

def glue_app(name: str):
    """Create GLUE application with minimal boilerplate"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def tool(name: str, **config) -> Any:
    """Create a tool with minimal configuration"""
    # Get tool type from mapping
    tool_type = TOOL_TYPES.get(name.lower())
    if tool_type is None:
        raise ValueError(f"Unknown tool type: {name}")
    
    # Get the tool's __init__ parameters
    init_params = inspect.signature(tool_type.__init__).parameters
    
    # Filter config to only include parameters that the tool accepts
    filtered_config = {
        k: v for k, v in config.items() 
        if k in init_params and k not in ['self', 'args', 'kwargs']
    }
    
    return tool_type(**filtered_config)

def tape(tools: List[Any], **config) -> Dict[str, Any]:
    """Bind tools with tape (testing/development)"""
    return _bind_tools(tools, AdhesiveType.TAPE, config)

def velcro(tools: List[Any], **config) -> Dict[str, Any]:
    """Bind tools with velcro (swappable)"""
    return _bind_tools(tools, AdhesiveType.VELCRO, config)

def duct_tape(tools: List[Any], **config) -> Dict[str, Any]:
    """Bind tools with duct tape (error handling)"""
    return _bind_tools(tools, AdhesiveType.DUCT_TAPE, config)

def glue(tools: List[Any], **config) -> Dict[str, Any]:
    """Bind tools with glue (standard development)"""
    return _bind_tools(tools, AdhesiveType.GLUE, config)

def epoxy(tools: List[Any], **config) -> Dict[str, Any]:
    """Bind tools with epoxy (permanent config)"""
    return _bind_tools(tools, AdhesiveType.EPOXY, config)

def super_glue(tools: List[Any], **config) -> Dict[str, Any]:
    """Bind tools with super glue (production)"""
    return _bind_tools(tools, AdhesiveType.SUPER_GLUE, config)

def double_side_tape(operations: List[Any]) -> Any:
    """Create sequential operations chain"""
    from .chain import Chain
    chain = Chain()
    for op in operations:
        chain.add_operation(op)
    return chain

def _bind_tools(
    tools: List[Any],
    adhesive: AdhesiveType,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Bind tools with specified adhesive"""
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t._adhesive = adhesive
        bound_tools[name] = t
    return bound_tools

__all__ = [
    'workspace',
    'glue_app',
    'tool',
    'tape',
    'velcro',
    'duct_tape',
    'glue',
    'epoxy',
    'super_glue',
    'double_side_tape',
    'AdhesiveType'
]
