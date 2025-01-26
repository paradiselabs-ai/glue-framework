"""Simplified Resource Base System"""

from typing import Dict, Set, Optional, Any
from dataclasses import dataclass
from .state import ResourceState, StateManager
from .simple_tool_binding import SimpleToolBinding
from .types import AdhesiveType

@dataclass
class ResourceMetadata:
    """Resource metadata"""
    category: str
    tags: Set[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = set()

class SimpleResource:
    """
    Simplified resource base class following Anthropic's guidelines.
    
    Features:
    - Two states: IDLE and ACTIVE
    - Simple tool bindings
    - Basic field management
    - Focus on natural model behavior
    """
    
    def __init__(
        self,
        name: str,
        category: str = "default",
        tags: Optional[Set[str]] = None,
        tool_bindings: Optional[Dict[str, AdhesiveType]] = None
    ):
        """Initialize resource"""
        self.name = name
        self.metadata = ResourceMetadata(
            category=category,
            tags=tags or set()
        )
        
        # Simple state management
        self._state_manager = StateManager()
        self._field = None
        self._registry = None
        self._context = None
        
        # Tool binding management
        self._tools: Dict[str, Any] = {}
        self._tool_bindings: Dict[str, SimpleToolBinding] = {}
        if tool_bindings:
            for tool_name, strength in tool_bindings.items():
                self.bind_tool(tool_name, strength)
    
    @property
    async def state(self) -> ResourceState:
        """Get current state"""
        return await self._state_manager.get_state(self.name)
    
    async def transition_to_active(self) -> bool:
        """Transition to ACTIVE state"""
        return await self._state_manager.transition_to_active(self.name)
    
    async def transition_to_idle(self) -> bool:
        """Transition to IDLE state"""
        return await self._state_manager.transition_to_idle(self.name)
    
    def bind_tool(self, tool_name: str, binding_type: AdhesiveType) -> None:
        """Bind a tool with specified adhesive type"""
        if binding_type == AdhesiveType.TAPE:
            binding = SimpleToolBinding.tape()
        elif binding_type == AdhesiveType.VELCRO:
            binding = SimpleToolBinding.velcro()
        elif binding_type == AdhesiveType.GLUE:
            binding = SimpleToolBinding.glue()
        else:
            raise ValueError(f"Invalid binding type: {binding_type}")
            
        self._tool_bindings[tool_name] = binding
    
    def get_tool_binding(self, tool_name: str) -> Optional[SimpleToolBinding]:
        """Get binding configuration for a tool"""
        return self._tool_bindings.get(tool_name)
    
    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """Use a tool with binding rules"""
        binding = self.get_tool_binding(tool_name)
        if not binding:
            raise ValueError(f"No binding found for tool: {tool_name}")
        
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Execute tool
        result = await tool.execute(**kwargs)
        
        # Break TAPE bindings after use
        if binding.type == AdhesiveType.TAPE:
            self._tools.pop(tool_name)
            self._tool_bindings.pop(tool_name)
        
        return result
    
    async def enter_field(self, field: 'MagneticField', registry: Optional['ResourceRegistry'] = None) -> None:
        """Enter a magnetic field"""
        self._field = field
        if registry:
            self._registry = registry

    async def exit_field(self) -> None:
        """Exit current field"""
        self._field = None
        self._registry = None
        self._context = None

    async def update_context(self, context: 'ContextState') -> None:
        """Update resource context"""
        self._context = context

    def __str__(self) -> str:
        """String representation"""
        return f"Resource({self.name}, category={self.metadata.category})"
