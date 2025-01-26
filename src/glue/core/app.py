"""GLUE Application Core"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, Field

from .model import Model
from .types import ResourceState, Message, MessageType, AdhesiveType
from .simple_resource import SimpleResource
from ..tools.simple_base import SimpleBaseTool

@dataclass
class AppMemory:
    """Application memory entry"""
    type: str
    content: Any
    field: Optional[str] = None
    timestamp: Optional[datetime] = None

    adhesive_type: Optional[AdhesiveType] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class AppConfig:
    """Application configuration"""
    name: str
    default_adhesive: AdhesiveType = AdhesiveType.VELCRO
    memory_limit: int = 1000
    enable_persistence: bool = False

class GlueApp:
    """
    Main GLUE application class.
    
    Features:
    - Simple field management with adhesive types
    - Basic memory management with adhesive tracking
    - Tool distribution with adhesive bindings
    - Clean resource handling
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[AppConfig] = None
    ):
        self.name = name
        self.config = config or AppConfig(name=name)
        
        # Core components
        self.fields: Dict[str, List[SimpleResource]] = {}
        self._memory: List[AppMemory] = []
        self._default_field: Optional[str] = None
        
        # Track active tools and their adhesive types
        self._tool_adhesives: Dict[str, Dict[str, AdhesiveType]] = {}
        
    def add_field(
        self,
        name: str,
        lead: Optional[Model] = None,
        members: Optional[List[Model]] = None,
        tools: Optional[List[SimpleBaseTool]] = None,
        adhesive_type: Optional[AdhesiveType] = None
    ) -> None:
        """Add a new field to the app"""
        if name in self.fields:
            raise ValueError(f"Field {name} already exists")
            
        field_resources = []
        
        # Add lead first if provided
        if lead:
            field_resources.append(lead)
            
        # Add other members
        if members:
            field_resources.extend(members)
                
        # Add tools with adhesive types
        if tools:
            self._tool_adhesives[name] = {}
            for tool in tools:
                tool_adhesive = adhesive_type or self.config.default_adhesive
                self._tool_adhesives[name][tool.name] = tool_adhesive
                field_resources.append(tool)
                
        # Store field
        self.fields[name] = field_resources
        
        # Set as default if first field
        if not self._default_field:
            self._default_field = name
        
    async def process_prompt(self, prompt: str) -> str:
        """Process a prompt using the default field"""
        if not self._default_field or self._default_field not in self.fields:
            raise ValueError("No default field available")
            
        try:
            # Store prompt in memory with default adhesive
            self._add_memory(AppMemory(
                type='prompt',
                content=prompt,
                adhesive_type=self.config.default_adhesive
            ))
            
            # Get lead model from default field
            field_resources = self.fields[self._default_field]
            lead_model = next(
                (r for r in field_resources if isinstance(r, Model)),
                None
            )
            
            if not lead_model:
                raise ValueError("No model available in default field")
            
            # Let model process prompt
            response = await lead_model.generate(prompt)
            
            # Store response in memory with adhesive type
            adhesive_type = self._tool_adhesives.get(self._default_field, {}).get(
                lead_model.name,
                self.config.default_adhesive
            )
            self._add_memory(AppMemory(
                type='response',
                content=response,
                field=self._default_field,
                adhesive_type=adhesive_type
            ))
            
            return response
            
        except Exception as e:
            # Store error in memory
            self._add_memory(AppMemory(
                type='error',
                content=str(e),
                adhesive_type=AdhesiveType.VELCRO  # Errors are temporary
            ))
            raise
        
    def _add_memory(self, entry: AppMemory) -> None:
        """Add entry to memory with limit handling"""
        self._memory.append(entry)
        
        # Enforce memory limit based on adhesive type
        if entry.adhesive_type == AdhesiveType.VELCRO:
            # Keep only recent VELCRO entries
            velcro_entries = [m for m in self._memory if m.adhesive_type == AdhesiveType.VELCRO]
            if len(velcro_entries) > self.config.memory_limit // 2:  # Use half the limit for VELCRO
                self._memory.remove(velcro_entries[0])
        else:
            # Enforce overall limit
            while len(self._memory) > self.config.memory_limit:
                # Remove oldest VELCRO entry first, then others
                velcro_entry = next(
                    (m for m in self._memory if m.adhesive_type == AdhesiveType.VELCRO),
                    None
                )
                if velcro_entry:
                    self._memory.remove(velcro_entry)
                else:
                    self._memory.pop(0)
        
    def get_memory(
        self,
        limit: Optional[int] = None,
        adhesive_type: Optional[AdhesiveType] = None
    ) -> List[AppMemory]:
        """Get filtered app memory"""
        # Filter by adhesive type if specified
        memory = self._memory
        if adhesive_type:
            memory = [m for m in memory if m.adhesive_type == adhesive_type]
            
        # Apply limit
        if limit:
            memory = memory[-limit:]
            
        return memory
        
    def get_field_resources(self, name: str) -> Optional[List[SimpleResource]]:
        """Get resources in a field by name"""
        return self.fields.get(name)
        
    def list_fields(self) -> List[str]:
        """List all field names"""
        return list(self.fields.keys())
        
    def get_default_field(self) -> Optional[str]:
        """Get the default field name"""
        return self._default_field
        
    def set_default_field(self, field_name: str) -> None:
        """Set the default field"""
        if field_name not in self.fields:
            raise ValueError(f"Field {field_name} not found")
        self._default_field = field_name
        
    async def cleanup(self) -> None:
        """Clean up app resources"""
        # Clean up all resources
        for field_resources in self.fields.values():
            for resource in field_resources:
                if hasattr(resource, 'cleanup'):
                    await resource.cleanup()
        
        # Clear all tracking
        self.fields.clear()
        self._tool_adhesives.clear()
        
        # Clear memory based on persistence and adhesive types
        if not self.config.enable_persistence:
            self._memory = [
                m for m in self._memory
                if m.adhesive_type == AdhesiveType.GLUE  # Keep only GLUE memories
            ]
            
        # Clear default field
        self._default_field = None
