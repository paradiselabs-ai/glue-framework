# src/glue/core/simple_app.py

"""Simplified GLUE Application Core"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from .model import Model
from .types import ResourceState, Message, MessageType
from .simple_resource import SimpleResource
from ..tools.simple_base import SimpleBaseTool

class SimpleGlueApp:
    """
    Simplified GLUE application class.
    
    Features:
    - Basic field management
    - Memory management
    - Tool distribution
    """
    
    def __init__(self, name: str):
        self.name = name
        self.fields: Dict[str, List[SimpleResource]] = {}
        self._memory: List[Dict[str, Any]] = []
        self._default_field: Optional[str] = None
        
    def add_field(
        self,
        name: str,
        lead: Optional[Model] = None,
        members: Optional[List[Model]] = None,
        tools: Optional[List[SimpleBaseTool]] = None
    ) -> None:
        """Add a new field to the app"""
        field_resources = []
        
        # Add lead first if provided
        if lead:
            field_resources.append(lead)
            
        # Add other members
        if members:
            field_resources.extend(members)
                
        # Add tools
        if tools:
            field_resources.extend(tools)
                
        # Store field
        self.fields[name] = field_resources
        
        # Set as default if first field
        if not self._default_field:
            self._default_field = name
            
    async def process_prompt(self, prompt: str) -> str:
        """Process a prompt using the default field"""
        # Store prompt in memory
        self._memory.append({
            'type': 'prompt',
            'content': prompt,
            'timestamp': datetime.now()
        })
        
        if not self._default_field or self._default_field not in self.fields:
            raise ValueError("No default field available")
        
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
        
        # Store response in memory
        self._memory.append({
            'type': 'response',
            'field': self._default_field,
            'content': response,
            'timestamp': datetime.now()
        })
        
        return response
        
    def get_memory(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get app memory up to limit"""
        return self._memory[-limit:]
        
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
        
        self.fields.clear()
        self._memory.clear()
        self._default_field = None
