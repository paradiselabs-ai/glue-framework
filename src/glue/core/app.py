"""GLUE Application Core"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from .model import Model
from ..tools.base import BaseTool
from ..magnetic.field import MagneticField
from .team import TeamRole

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
        config: Optional[AppConfig] = None,
        workspace_path: Optional[str] = None
    ):
        self.name = name
        self.config = config or AppConfig(name=name)
        self.workspace_path = workspace_path
        
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
        
        # Set researchers as default field if it exists
        if name == "researchers":
            self._default_field = name
        # Otherwise set as default if first field
        elif not self._default_field:
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
            
            # Get team lead
            team = self.teams[self._default_field]
            lead_name = next(
                (m for m in team.members if team.get_member_role(m) == TeamRole.LEAD),
                None
            )
            if not lead_name:
                raise ValueError("No team lead available")
                
            lead_model = self.models[lead_name]
            
            # Generate response through team lead
            response = await lead_model.generate(prompt)
            
            # Store full response in memory
            self._add_memory(AppMemory(
                type='internal',
                content=response,
                field=self._default_field
            ))
            
            # Extract final result
            if "File saved at" in response:
                # File operation result
                start = response.find("File saved at")
                end = response.find("\n", start)
                if end == -1:
                    end = len(response)
                final_response = response[start:end]
            elif "Tool output:" in response:
                # Tool usage result
                start = response.find("Tool output:") + len("Tool output:")
                end = response.find("\n", start)
                if end == -1:
                    end = len(response)
                final_response = response[start:end].strip()
            else:
                # Default to last line that's not a thought or tool usage
                lines = [line.strip() for line in response.split("\n") 
                        if line.strip() and 
                        not line.strip().startswith("<") and 
                        not line.strip().endswith(">")]
                final_response = lines[-1] if lines else "Task completed"
            
            # Store final response
            self._add_memory(AppMemory(
                type='response',
                content=final_response,
                field=self._default_field
            ))
            
            return final_response
            
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
        """Register a team with the app and create corresponding field"""
        if name in self.teams:
            raise ValueError(f"Team {name} already registered")
            
        # Register team
        self.teams[name] = team
        
        # Get team's lead and members
        lead = next((self.models[m] for m in team.members if team.get_member_role(m) == TeamRole.LEAD), None)
        members = [self.models[m] for m in team.members if team.get_member_role(m) != TeamRole.LEAD]
        
        # Get team's tools
        tools = [self.tools[t] for t in team.tools]
        
        # Add field for team
        self.add_field(
            name=name,
            lead=lead,
            members=members,
            tools=tools
        )
        
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
