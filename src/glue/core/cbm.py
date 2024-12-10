# src/glue/core/cbm.py

"""Conversational Based Model Implementation"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from .model import Model
from .conversation import ConversationManager
from .adhesive import Adhesive, AdhesiveFactory, AdhesiveProperties
from .memory import MemoryManager
from .cbm_orchestrator import CBMOrchestrator
from .context import ContextState
from .logger import get_logger

class CBM:
    """
    Conversational Based Model - A single entity that wraps multiple models
    and synthesizes their interactions into unified responses.
    """
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.models: Dict[str, Model] = {}
        self.memory_manager = MemoryManager()
        
        # Internal orchestration
        self.orchestrator = CBMOrchestrator(f"{name}_orchestrator")
        
        # Binding patterns for external interactions
        self.bindings: Dict[str, List[tuple[str, str, Adhesive]]] = {
            'glue': [],      # Permanent bindings
            'velcro': [],    # Swappable bindings
            'tape': [],      # Temporary test bindings
            'magnet': []     # Dynamic bindings
        }
        self.adhesive_factory = AdhesiveFactory()
        
    async def add_model(self, model: Model) -> None:
        """Add a model to the CBM"""
        self.models[model.name] = model
        await self.orchestrator.add_model(model)
        
    def add_dependency(self, model: str, depends_on: str) -> None:
        """Add a dependency between models"""
        self.orchestrator.add_dependency(model, depends_on)
        
    def bind_to(
        self,
        other: 'CBM',
        binding_type: str = 'glue',
        properties: Optional[AdhesiveProperties] = None
    ) -> None:
        """Create a binding between this CBM and another"""
        # verify binding type is valid
        if binding_type not in self.bindings:
            raise ValueError(f"Unknown binding type: {binding_type}")
            
        # create adhesive instance
        if properties:
            adhesive = self.adhesive_factory.create_with_properties(binding_type, properties)
        else:
            adhesive = self.adhesive_factory.create(binding_type)
            
        # only bind if adhesive is valid
        if adhesive.can_bind():
            self.bindings[binding_type].append((self.name, other.name, adhesive))
            adhesive.use()
            self.memory_manager.share(
                from_model=self.name,
                to_model=other.name,
                key=f"binding_{binding_type}",
                content={
                    "type": binding_type,
                    "properties": properties.__dict__ if properties else None
                }
            )
        else:
            raise ValueError(f"Adhesive of type {binding_type} cannot create new bindings")
            
    def get_active_bindings(self) -> Dict[str, List[Tuple[str, str, float]]]:
        """Get all active bindings with their current strengths"""
        active_bindings = {}
        for binding_type, bindings in self.bindings.items():
            active = []
            for model1, model2, adhesive in bindings:
                if adhesive.can_bind():
                    strength = adhesive.get_strength()
                    active.append((model1, model2, strength))
            active_bindings[binding_type] = active
        return active_bindings

    async def process_input(
        self,
        user_input: str,
        context: Optional[ContextState] = None
    ) -> str:
        """
        Process user input through the CBM.
        This is the main entry point for CBM operations.
        """
        self.logger.debug(f"CBM {self.name} processing input: {user_input}")
        
        # Store input in memory
        self.memory_manager.store(
            key=f"input_{datetime.now().timestamp()}",
            content=user_input,
            memory_type="working"
        )
        
        # Process through internal orchestrator
        response = await self.orchestrator.process(user_input, context)
        
        # Store response in memory
        self.memory_manager.store(
            key=f"response_{datetime.now().timestamp()}",
            content=response,
            memory_type="short_term"
        )
        
        return response
    
    async def cleanup(self) -> None:
        """Clean up CBM resources"""
        await self.orchestrator.cleanup()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert CBM to dictionary for serialization"""
        return {
            'name': self.name,
            'models': {
                name: {
                    'name': model.name,
                    'provider': model.provider,
                    'role': model.role,
                    'config': model.config.__dict__
                } 
                for name, model in self.models.items()
            },
            'bindings': {
                binding_type: [
                    {
                        'model1': model1,
                        'model2': model2,
                        'strength': adhesive.get_strength()
                    }
                    for model1, model2, adhesive in bindings
                ]
                for binding_type, bindings in self.bindings.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CBM':
        """Create CBM from dictionary"""
        cbm = cls(data['name'])
        
        # Recreate models
        for model_name, model_data in data['models'].items():
            model = Model(
                name=model_data['name'],
                provider=model_data['provider']
            )
            model.role = model_data['role']
            cbm.add_model(model)
        
        # Recreate bindings
        for binding_type, bindings in data['bindings'].items():
            for binding in bindings:
                cbm.bind_models(
                    binding['model1'],
                    binding['model2'],
                    binding_type
                )
        
        return cbm
