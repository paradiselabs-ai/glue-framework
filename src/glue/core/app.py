"""GLUE Application Core"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from .model import Model
from ..tools.base import BaseTool
from ..magnetic.field import MagneticField

@dataclass
class AppMemory:
    """Application memory entry"""
    type: str  # 'prompt', 'response', or 'error'
    content: Any
    field: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class AppConfig:
    """Application configuration"""
    name: str
    memory_limit: int = 1000
    enable_persistence: bool = False

class GlueApp:
    """
    Main GLUE application class.
    
    Features:
    - Field management for models and tools
    - Basic memory for user interactions
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
        self.fields: Dict[str, List[Any]] = {}
        self.tools: Dict[str, BaseTool] = {}
        self.models: Dict[str, Model] = {}
        self.teams: Dict[str, Any] = {}  # Will store Team objects
        self.magnetic_field: Optional[MagneticField] = None
        self._memory: List[AppMemory] = []
        self._default_field: Optional[str] = None
        
    def add_field(
        self,
        name: str,
        lead: Optional[Model] = None,
        members: Optional[List[Model]] = None,
        tools: Optional[List[BaseTool]] = None
    ) -> None:
        """Add a new field to the app"""
        if name in self.fields:
            raise ValueError(f"Field {name} already exists")
            
        # Collect field resources
        field_resources = []
        if lead:
            field_resources.append(lead)
        if members:
            field_resources.extend(members)
        if tools:
            field_resources.extend(tools)
                
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
            # Store prompt in memory
            self._add_memory(AppMemory(
                type='prompt',
                content=prompt
            ))
            
            # Get lead model
            field_resources = self.fields[self._default_field]
            lead_model = next(
                (r for r in field_resources if isinstance(r, Model)),
                None
            )
            if not lead_model:
                raise ValueError("No model available in default field")
            
            # Generate response
            response = await lead_model.generate(prompt)
            
            # Store response
            self._add_memory(AppMemory(
                type='response',
                content=response,
                field=self._default_field
            ))
            
            return response
            
        except Exception as e:
            # Store error
            self._add_memory(AppMemory(
                type='error',
                content=str(e)
            ))
            raise
        
    def _add_memory(self, entry: AppMemory) -> None:
        """Add entry to memory with limit handling"""
        self._memory.append(entry)
        
        # Enforce memory limit
        while len(self._memory) > self.config.memory_limit:
            self._memory.pop(0)  # Remove oldest entry
        
    def get_memory(
        self,
        limit: Optional[int] = None
    ) -> List[AppMemory]:
        """Get app memory up to limit"""
        memory = self._memory
        if limit:
            memory = memory[-limit:]
        return memory
        
    def get_field_resources(self, name: str) -> Optional[List[Any]]:
        """Get resources in a field by name"""
        return self.fields.get(name)
        
    def list_fields(self) -> List[str]:
        """List all field names"""
        return list(self.fields.keys())
        
    def register_model(self, name: str, model: Model) -> None:
        """Register a model with the app"""
        if name in self.models:
            raise ValueError(f"Model {name} already registered")
        self.models[name] = model

    def register_team(self, name: str, team: Any) -> None:
        """Register a team with the app"""
        if name in self.teams:
            raise ValueError(f"Team {name} already registered")
        self.teams[name] = team
        
    def set_magnetic_field(self, field: MagneticField) -> None:
        """Set the magnetic field for team interactions"""
        self.magnetic_field = field

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
        
        # Clear fields
        self.fields.clear()
        self._default_field = None
        
        # Clear memory if not persistent
        if not self.config.enable_persistence:
            self._memory.clear()
