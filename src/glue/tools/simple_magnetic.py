# src/glue/tools/simple_magnetic.py

"""Simplified Magnetic Tool Implementation"""

import asyncio
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from .simple_base import SimpleBaseTool
from ..core.simple_resource import SimpleResource
from ..core.state import ResourceState
from ..core.types import AdhesiveType
from ..magnetic.rules import InteractionPattern

@dataclass
class SimpleMagneticTool(SimpleBaseTool):
    """
    Simplified magnetic tool with basic resource sharing.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Basic resource sharing
    - Adhesive-based persistence
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        shared_resources: Optional[List[str]] = None,
        sticky: bool = False,
        binding_type: AdhesiveType = AdhesiveType.VELCRO,
        **kwargs
    ):
        super().__init__(
            name=name,
            description=description,
            sticky=sticky,
            **kwargs
        )
        
        # Resource sharing
        self.shared_resources = shared_resources or []
        self.binding_type = binding_type
        self._shared_data: Dict[str, Any] = {}
        self._attracted_to: Set[SimpleResource] = set()
        self._workspace = None

    async def share_resource(self, resource_name: str, data: Any) -> None:
        """Share a resource with other tools"""
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        
        # Store data
        self._shared_data[resource_name] = data
        
        # Share with attracted tools
        for tool in self._attracted_to:
            if isinstance(tool, SimpleMagneticTool):
                tool._shared_data[resource_name] = data

    def get_shared_resource(self, resource_name: str) -> Optional[Any]:
        """Get a shared resource"""
        if resource_name not in self.shared_resources:
            raise ValueError(f"Resource {resource_name} not declared as shareable")
        
        # Check local data first
        if resource_name in self._shared_data:
            return self._shared_data[resource_name]
        
        # Check attracted tools
        for tool in self._attracted_to:
            if isinstance(tool, SimpleMagneticTool):
                if resource_name in tool._shared_data:
                    return tool._shared_data[resource_name]
        
        return None

    async def attract_to(self, other: SimpleResource) -> bool:
        """Create attraction to another resource"""
        if other not in self._attracted_to:
            self._attracted_to.add(other)
            if hasattr(other, '_attracted_to'):
                other._attracted_to.add(self)
            return True
        return False

    async def break_attraction(self, other: SimpleResource) -> None:
        """Break attraction with another resource"""
        self._attracted_to.discard(other)
        if hasattr(other, '_attracted_to'):
            other._attracted_to.discard(self)

    async def attach_to_workspace(self, workspace) -> None:
        """Attach tool to a workspace"""
        self._workspace = workspace
        
        # Load persistent data if sticky
        if self.sticky and hasattr(workspace, 'load_tool_data'):
            data = await workspace.load_tool_data(self.name)
            if data:
                self._shared_data.update(data)

    async def detach_from_workspace(self) -> None:
        """Detach tool from workspace"""
        if self._workspace:
            # Save data if sticky
            if self.sticky and hasattr(self._workspace, 'save_tool_data'):
                await self._workspace.save_tool_data(self.name, self._shared_data)
            self._workspace = None

    async def cleanup(self) -> None:
        """Clean up resources"""
        # Break all attractions
        for other in list(self._attracted_to):
            await self.break_attraction(other)
        
        # Detach from workspace
        await self.detach_from_workspace()
        
        # Clear shared data based on binding type
        if self.binding_type == AdhesiveType.TAPE:
            self._shared_data.clear()
        elif self.binding_type == AdhesiveType.VELCRO and not self.sticky:
            self._shared_data.clear()
        
        await super().cleanup()

    def __str__(self) -> str:
        status = f"{self.name}: {self.description}"
        if self.shared_resources:
            status += f" (Shares: {', '.join(self.shared_resources)})"
        if self.sticky:
            status += " (Sticky)"
        return status
