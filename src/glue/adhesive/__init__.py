# src/glue/adhesive/__init__.py

"""GLUE Adhesive System - High-level Magnetic Field Abstractions"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union
from dataclasses import dataclass
from functools import wraps

from ..core.types import ResourceState
from ..core.resource import Resource
from ..magnetic.field import MagneticField
from ..magnetic.rules import RuleSet, AttractionRule, PolicyPriority, AttractionPolicy
from ..core.registry import ResourceRegistry

class AdhesiveType(Enum):
    """Types of adhesive bonds mapped to magnetic behaviors"""
    # Temporary bindings (break after use)
    TAPE_ATTRACT = "tape_attract"    # Temporary bidirectional
    TAPE_PUSH = "tape_push"          # Temporary one-way send
    TAPE_PULL = "tape_pull"          # Temporary one-way receive
    TAPE_REPEL = "tape_repel"        # Temporary blocking
    
    # Flexible bindings (can reconnect)
    VELCRO_ATTRACT = "velcro_attract"  # Flexible bidirectional
    VELCRO_PUSH = "velcro_push"        # Flexible one-way send
    VELCRO_PULL = "velcro_pull"        # Flexible one-way receive
    VELCRO_REPEL = "velcro_repel"      # Flexible blocking
    
    # Persistent bindings (full context)
    GLUE_ATTRACT = "glue_attract"    # Persistent bidirectional
    GLUE_PUSH = "glue_push"          # Persistent one-way send
    GLUE_PULL = "glue_pull"          # Persistent one-way receive
    GLUE_REPEL = "glue_repel"        # Persistent blocking
    
    # Special bindings
    CHAT = "chat"                    # Direct model chat (<-->)

@dataclass
class FlowConfig:
    """Configuration for magnetic flow between resources"""
    source: str
    target: str
    type: str  # "><", "->", "<-", "<>", "<-->"
    adhesive: AdhesiveType

class Workspace:
    """Magnetic field workspace for resource interactions"""
    def __init__(self, name: str):
        self.name = name
        self.field: Optional[MagneticField] = None
        self.resources: Dict[str, Resource] = {}
        self.flows: List[FlowConfig] = []
    
    async def __aenter__(self) -> 'Workspace':
        """Enter workspace context"""
        registry = ResourceRegistry()
        self.field = MagneticField(self.name, registry)
        self.field._active = True  # Activate the field
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Exit workspace and cleanup resources"""
        if self.field:
            # Clean up resources first
            for resource in self.resources.values():
                await resource.exit_field()
            
            # Clean up field
            await self.field.cleanup()
            self.field = None
            self.resources.clear()
            self.flows.clear()

    async def add_resource(self, resource: Resource) -> None:
        """Add resource to workspace"""
        if self.field:
            await self.field.add_resource(resource)
            self.resources[resource.name] = resource

    async def setup_flow(self, flow: FlowConfig) -> None:
        """Configure magnetic flow between resources"""
        if not self.field:
            return

        # Validate flow type first
        if flow.type not in ["><", "->", "<-", "<>", "<-->"]:
            raise ValueError(f"Invalid flow type: {flow.type}")

        source = self.resources.get(flow.source)
        target = self.resources.get(flow.target)
        if not (source and target):
            return

        # Configure magnetic behavior based on adhesive type
        adhesive = flow.adhesive
        if adhesive.name.startswith('TAPE'):
            source._break_after_use = True
            target._break_after_use = True
        elif adhesive.name.startswith('VELCRO'):
            source._allow_reconnect = True
            target._allow_reconnect = True
        elif adhesive.name.startswith('GLUE'):
            source._persist_context = True
            target._persist_context = True

        # Helper to set mode - only preserve bidirectional against repel
        def set_mode(resource: Resource, new_mode: str) -> None:
            current_mode = getattr(resource, "_attract_mode", "none")
            # Only preserve bidirectional against repel
            if not (current_mode == "bidirectional" and new_mode == "repel"):
                resource._attract_mode = new_mode

        # Setup magnetic flow
        if flow.type == "><":  # Bidirectional
            await self.field.attract(source, target)
            await self.field.attract(target, source)
            set_mode(source, "bidirectional")
            set_mode(target, "bidirectional")
        elif flow.type == "->":  # Source to target
            await self.field.attract(source, target)
            set_mode(source, "push")
            set_mode(target, "receive")
        elif flow.type == "<-":  # Target from source
            await self.field.attract(target, source)
            set_mode(source, "receive")
            set_mode(target, "push")
        elif flow.type == "<>":  # Repulsion
            await self.field.repel(source, target)
            await self.field.repel(target, source)
            set_mode(source, "repel")
            set_mode(target, "repel")
        elif flow.type == "<-->":  # Direct chat
            await self.field.enable_chat(source, target)
            set_mode(source, "chat")
            set_mode(target, "chat")

        self.flows.append(flow)

def workspace_context(name: str) -> Workspace:
    """Create a workspace context"""
    return Workspace(name)

def glue_app(name: str):
    """Create GLUE application with magnetic field support"""
    def decorator(func: Any):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with workspace_context(name) as ws:
                return await func(ws, *args, **kwargs)
        return wrapper
    return decorator

def bind_magnetic(source: Resource, target: Resource, adhesive: AdhesiveType) -> None:
    """Configure magnetic binding between resources"""
    # Configure binding behavior
    if adhesive.name.startswith('TAPE'):
        source._break_after_use = True
        target._break_after_use = True
    elif adhesive.name.startswith('VELCRO'):
        source._allow_reconnect = True
        target._allow_reconnect = True
    elif adhesive.name.startswith('GLUE'):
        source._persist_context = True
        target._persist_context = True
    
    # Configure magnetic behavior
    if '_ATTRACT' in adhesive.name:
        source._attract_mode = 'bidirectional'
        target._attract_mode = 'bidirectional'
    elif '_PUSH' in adhesive.name:
        source._attract_mode = 'push'
        target._attract_mode = 'receive'
    elif '_PULL' in adhesive.name:
        source._attract_mode = 'receive'
        target._attract_mode = 'push'
    elif '_REPEL' in adhesive.name:
        source._attract_mode = 'repel'
        target._attract_mode = 'repel'
    elif adhesive == AdhesiveType.CHAT:
        source._attract_mode = 'chat'
        target._attract_mode = 'chat'

def flow(source: str, target: str, type: str = "><", adhesive: AdhesiveType = AdhesiveType.GLUE_ATTRACT) -> FlowConfig:
    """Define magnetic flow between resources"""
    return FlowConfig(source, target, type, adhesive)

def tape(tools: List[Any], **config) -> Dict[str, Any]:
    """Create tools with temporary (TAPE) binding"""
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t._adhesive = AdhesiveType.TAPE_ATTRACT
        t._break_after_use = True
        t._attract_mode = "bidirectional"
        # Clear other binding attributes
        if hasattr(t, '_allow_reconnect'): delattr(t, '_allow_reconnect')
        if hasattr(t, '_persist_context'): delattr(t, '_persist_context')
        bound_tools[name] = t
    return bound_tools

def velcro(tools: List[Any], **config) -> Dict[str, Any]:
    """Create tools with flexible (VELCRO) binding"""
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t._adhesive = AdhesiveType.VELCRO_ATTRACT
        t._allow_reconnect = True
        t._attract_mode = "bidirectional"
        # Clear other binding attributes
        if hasattr(t, '_break_after_use'): delattr(t, '_break_after_use')
        if hasattr(t, '_persist_context'): delattr(t, '_persist_context')
        bound_tools[name] = t
    return bound_tools

def glue(tools: List[Any], **config) -> Dict[str, Any]:
    """Create tools with persistent (GLUE) binding"""
    bound_tools = {}
    for t in tools:
        name = getattr(t, "name", t.__class__.__name__.lower())
        t._adhesive = AdhesiveType.GLUE_ATTRACT
        t._persist_context = True
        t._attract_mode = "bidirectional"
        # Clear other binding attributes
        if hasattr(t, '_break_after_use'): delattr(t, '_break_after_use')
        if hasattr(t, '_allow_reconnect'): delattr(t, '_allow_reconnect')
        bound_tools[name] = t
    return bound_tools

def tool(tool_type_name: str, **config) -> Any:
    """Create a tool with optional configuration"""
    # Get tool type from mapping
    tool_type = _infer_tool_type(tool_type_name)
    if tool_type is None:
        raise ValueError(f"Unknown tool type: {tool_type_name}")
    
    # Get the tool's __init__ parameters
    init_params = {
        'name': tool_type_name,  # Default name is the tool type
        'description': f"{tool_type_name} tool",  # Default description
        'config': None,  # Will be created by BaseTool
        'permissions': None  # Will be created by BaseTool
    }
    
    # Override defaults with provided config
    init_params.update(config)
    
    return tool_type(**init_params)

def _infer_tool_type(name: str) -> Optional[Type[Any]]:
    """Infer tool type from name"""
    from ..tools import TOOL_TYPES
    return TOOL_TYPES.get(name.lower())

__all__ = [
    'workspace_context',
    'glue_app',
    'bind_magnetic',
    'flow',
    'tape',
    'velcro',
    'glue',
    'tool',
    'AdhesiveType',
    'FlowConfig'
]
