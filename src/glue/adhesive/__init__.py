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
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Exit workspace and cleanup resources"""
        if self.field:
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

        # Setup magnetic flow
        if flow.type == "><":  # Bidirectional
            await self.field.attract(source, target)
            await self.field.attract(target, source)
        elif flow.type == "->":  # Source to target
            await self.field.attract(source, target)
        elif flow.type == "<-":  # Target from source
            await self.field.attract(target, source)
        elif flow.type == "<>":  # Repulsion
            await self.field.repel(source, target)
            await self.field.repel(target, source)
        elif flow.type == "<-->":  # Direct chat
            await self.field.enable_chat(source, target)

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

__all__ = [
    'workspace_context',
    'glue_app',
    'bind_magnetic',
    'flow',
    'AdhesiveType',
    'FlowConfig'
]
