# src/glue/core/cbm.py
#======================IMPORTS======================
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from .model import Model
from .conversation import ConversationManager
from .adhesive import Adhesive, AdhesiveFactory, AdhesiveProperties
from .memory import MemoryManager

#======================CLASS======================
class CBM:
    """Conversational Based Model - manages multiple models as one entity"""
    def __init__(self, name: str):
        self.name = name
        self.models: Dict[str, Model] = {}
        self.conversation_manager = ConversationManager()
        # update binding patterns to store actual Adhesive instances
        self.bindings: Dict[str, List[tuple[str, str, Adhesive]]] = {
            'glue': [],      # Permanent bindings
            'velcro': [],    # Swappable bindings
            'tape': [],      # Temporary test bindings
            'magnet': []     # Dynamic bindings
        }
        self.adhesive_factory = AdhesiveFactory()
        self.memory_manager = MemoryManager()
        
# ==============MODEL MANAGEMENT================

    def add_model(self, model: Model) -> None:
        """Add a model to the CBM"""
        self.models[model.name] = model
        
# ==============BINDING MANAGEMENT================

    def bind_models(self, model1_name: str, model2_name: str, binding_type: str = 'glue', properties: Optional[AdhesiveProperties] = None) -> None:
        """Create a binding between two models"""
        # verify binding type is valid
        if binding_type not in self.bindings:
            raise ValueError(f"Unknown binding type: {binding_type}")
            
        # Verify both models exist
        if model1_name not in self.models:
            raise KeyError(f"Model {model1_name} not found")
        if model2_name not in self.models:
            raise KeyError(f"Model {model2_name} not found")
            
        model1 = self.models[model1_name]
        model2 = self.models[model2_name]
        
        # create adhesive instance
        if properties:
            adhesive = self.adhesive_factory.create_with_properties(binding_type, properties)
        else:
            adhesive = self.adhesive_factory.create(binding_type)
            
        # only bind if adhesive is valid
        if adhesive.can_bind():
            self.bindings[binding_type].append((model1_name, model2_name, adhesive))
            model1.bind_to(model2, binding_type)
            model2.bind_to(model1, binding_type)
            adhesive.use()
            self.memory_manager.share(
                from_model=model1_name,
                to_model=model2_name,
                key=f"binding_{binding_type}",
                content={
                    "type": binding_type,
                    "properties": properties.__dict__ if properties else None
                }
            )
            
        else:
            raise ValueError(f"Adhesive of type {binding_type} cannot create new bindings")
        
#====================Active Bindings====================
        
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

#====================PROCESS INPUT====================

    async def process_input(self, user_input: str) -> str:
        """Process user input through the CBM"""
        self.memory_manager.store(
            key=f"input_{datetime.now().timestamp()}",
            content=user_input,
            memory_type="working"
        )
        
        #Get only active bindings for processing
        active_bindings = self.get_active_bindings()
        return await self.conversation_manager.process(
            self.models,
            active_bindings,
            user_input
        )
        
        self.memory_manager.store(
            key=f"response_{datetime.now().timestamp()}",
            content=response,
            memory_type="short_term"
        )
        
        return response
    
# =================SERIALIZATION=================

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
            for mbinding in bindings:
                cbm.bind_models(
                    mbinding['model1'],
                    mbinding['model2'],
                    binding_type
                )
        
        return cbm