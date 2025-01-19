"""GLUE Application Core"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from .model import Model
from .types import ResourceState, Message, MessageType
from ..magnetic.field import MagneticField
from ..tools.base import BaseTool

class GlueApp:
    """
    Main GLUE application class.
    
    Features:
    - Field coordination
    - Smart routing
    - Memory management
    - Tool distribution
    """
    
    def __init__(self, name: str):
        self.name = name
        self.fields: Dict[str, MagneticField] = {}
        self._memory: List[Dict[str, Any]] = []
        self._default_field: Optional[MagneticField] = None
        
    def add_field(
        self,
        name: str,
        lead: Optional[Model] = None,
        members: Optional[List[Model]] = None,
        tools: Optional[List[BaseTool]] = None
    ) -> MagneticField:
        """Add a new field to the app"""
        field = MagneticField(name=name, registry=self)
        
        # Add lead first if provided
        if lead:
            field.add_resource(lead, is_lead=True)
            
        # Add other members
        if members:
            for member in members:
                field.add_resource(member)
                
        # Add tools
        if tools:
            for tool in tools:
                field.add_resource(tool)
                
        # Store field
        self.fields[name] = field
        
        # Set as default if first field
        if not self._default_field:
            self._default_field = field
            
        return field
        
    async def process_prompt(self, prompt: str) -> str:
        """Process a prompt using the most appropriate field"""
        # Store prompt in memory
        self._memory.append({
            'type': 'prompt',
            'content': prompt,
            'timestamp': datetime.now()
        })
        
        # Find best field
        best_field = self._default_field
        best_score = 0.0
        
        for field in self.fields.values():
            score = await field.handles_intent(prompt)
            if score > best_score:
                best_score = score
                best_field = field
                
        # Let field process prompt
        response = await best_field.process_prompt(prompt)
        
        # Store response in memory
        self._memory.append({
            'type': 'response',
            'field': best_field.name,
            'content': response,
            'timestamp': datetime.now()
        })
        
        return response
        
    def get_memory(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get app memory up to limit"""
        return self._memory[-limit:]
        
    def get_field(self, name: str) -> Optional[MagneticField]:
        """Get a field by name"""
        return self.fields.get(name)
        
    def list_fields(self) -> List[str]:
        """List all field names"""
        return list(self.fields.keys())
        
    def get_default_field(self) -> Optional[MagneticField]:
        """Get the default field"""
        return self._default_field
        
    def set_default_field(self, field: MagneticField) -> None:
        """Set the default field"""
        if field.name not in self.fields:
            raise ValueError(f"Field {field.name} not found")
        self._default_field = field
        
    async def cleanup(self) -> None:
        """Clean up app resources"""
        for field in self.fields.values():
            await field.cleanup()
        self.fields.clear()
        self._memory.clear()
        self._default_field = None
