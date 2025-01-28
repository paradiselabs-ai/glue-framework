"""GLUE Adhesive System - Model-to-Tool Binding Management"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union
from dataclasses import dataclass
from functools import wraps

from ..core.types import AdhesiveType, AdhesiveState, AdhesiveProperties

class AdhesiveType(Enum):
    """Types of adhesive bonds for model-to-tool bindings"""
    # Temporary binding - breaks after use
    TAPE = "tape"          # Single-use binding that breaks after use
    
    # Flexible binding - persists for session
    VELCRO = "velcro"      # Session-level binding that can be reattached
    
    # Permanent binding - persists across sessions
    GLUE = "glue"          # Permanent binding with full context sharing

def tape(tools: List[Any], **config) -> Dict[str, Any]:
    """Configure tools with temporary (TAPE) binding
    
    TAPE bindings break after a single use, ensuring tools don't maintain
    state between uses. This is useful for stateless operations or when
    you want to ensure fresh tool state for each use.
    """
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t.binding_type = AdhesiveType.TAPE
        t.break_after_use = True
        bound_tools[name] = t
    return bound_tools

def velcro(tools: List[Any], **config) -> Dict[str, Any]:
    """Configure tools with session (VELCRO) binding
    
    VELCRO bindings persist for the duration of a session but can be
    detached and reattached. This allows tools to maintain state during
    a session while still being flexible about when they're used.
    """
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t.binding_type = AdhesiveType.VELCRO
        t.allow_reconnect = True
        bound_tools[name] = t
    return bound_tools

def glue(tools: List[Any], **config) -> Dict[str, Any]:
    """Configure tools with permanent (GLUE) binding
    
    GLUE bindings persist across sessions and maintain full context.
    This is useful for tools that need to maintain long-term state
    or when consistent tool state is important for operations.
    """
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t.binding_type = AdhesiveType.GLUE
        t.persist_context = True
        bound_tools[name] = t
    return bound_tools

def tool(tool_type_name: str, **config) -> Any:
    """Create a tool with optional configuration"""
    tool_type = _infer_tool_type(tool_type_name)
    if tool_type is None:
        raise ValueError(f"Unknown tool type: {tool_type_name}")
    
    init_params = {
        'name': tool_type_name,
        'description': f"{tool_type_name} tool",
        'config': None,
        'permissions': None
    }
    init_params.update(config)
    
    return tool_type(**init_params)

def _infer_tool_type(name: str) -> Optional[Type[Any]]:
    """Infer tool type from name"""
    from ..tools import TOOL_TYPES
    return TOOL_TYPES.get(name.lower())

__all__ = [
    'AdhesiveType',
    'tape',
    'velcro',
    'glue',
    'tool'
]
