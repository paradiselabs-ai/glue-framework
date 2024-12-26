# src/glue/core/cbm.py

"""Conversational Based Model Implementation"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from .model import Model
from .memory import MemoryManager
from .cbm_orchestrator import CBMOrchestrator
from .context import ContextState
from .logger import get_logger
from .binding import BindingConfig, AdhesiveType

class CBM:
    """
    Conversational Based Model - A single entity that wraps multiple models
    and synthesizes their interactions into unified responses.
    
    Features:
    - Type-safe binding system
    - State management
    - Memory integration
    - Error handling
    - Event propagation
    """
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.memory_manager = MemoryManager()
        self.orchestrator = CBMOrchestrator(f"{name}_orchestrator")
        
        # Error handling
        self.orchestrator.on_error(self._handle_error)
        
    async def add_model(
        self,
        model: Model,
        bindings: Optional[List[BindingConfig]] = None
    ) -> None:
        """
        Add a model to the CBM with optional bindings
        
        Args:
            model: Model to add
            bindings: Optional binding configurations
        """
        await self.orchestrator.add_model(model, bindings)
        
    def add_dependency(self, model: str, depends_on: str) -> None:
        """Add a dependency between models"""
        self.orchestrator.add_dependency(model, depends_on)
        
    def bind_models(
        self,
        source: str,
        target: str,
        binding_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Create a binding between models using adhesive metaphors
        
        Args:
            source: Source model name
            target: Target model name
            binding_type: Type of binding (tape, velcro, glue, magnet)
            properties: Optional binding properties
        """
        # Convert string type to AdhesiveType
        try:
            adhesive_type = AdhesiveType[binding_type.upper()]
        except KeyError:
            raise ValueError(f"Invalid binding type: {binding_type}")
        
        # Create appropriate binding config
        if adhesive_type == AdhesiveType.TAPE:
            duration = properties.get("duration", timedelta(minutes=30))
            config = BindingConfig.tape(source, target, duration)
            
        elif adhesive_type == AdhesiveType.VELCRO:
            attempts = properties.get("reconnect_attempts", 3)
            config = BindingConfig.velcro(source, target, attempts)
            
        elif adhesive_type == AdhesiveType.GLUE:
            strength = properties.get("strength", 1.0)
            config = BindingConfig.glue(source, target, strength)
            
        elif adhesive_type == AdhesiveType.MAGNET:
            polarity = properties.get("polarity", "attract")
            config = BindingConfig.magnet(source, target, polarity)
            
        # Add binding through orchestrator
        self.orchestrator.add_model(
            self.orchestrator.state.models[source],
            [config]
        )

    async def process_input(
        self,
        user_input: str,
        context: Optional[ContextState] = None
    ) -> str:
        """
        Process input through the CBM.
        
        Features:
        - Memory integration
        - Error handling
        - Event propagation
        
        Args:
            user_input: Input to process
            context: Optional context
            
        Returns:
            Final synthesized response
        """
        self.logger.debug(f"CBM {self.name} processing input: {user_input}")
        
        try:
            # Store input in memory
            self.memory_manager.store(
                key=f"input_{datetime.now().timestamp()}",
                content=user_input
            )
            
            # Process through orchestrator
            response = await self.orchestrator.process(user_input, context)
            
            # Store response in memory
            self.memory_manager.store(
                key=f"response_{datetime.now().timestamp()}",
                content=response
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing input: {e}")
            raise
    
    def _handle_error(self, source: str, error: Exception) -> None:
        """Handle errors from orchestrator"""
        self.logger.error(f"Error from {source}: {error}")
        # Add error handling logic here
        
    async def cleanup(self) -> None:
        """Clean up CBM resources"""
        await self.orchestrator.cleanup()
        self.memory_manager.clear()
    
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
                for name, model in self.orchestrator.state.models.items()
            },
            'bindings': [
                {
                    'type': binding.config.type.name,
                    'source': binding.config.source,
                    'target': binding.config.target,
                    'properties': binding.config.properties
                }
                for binding in self.orchestrator.state.bindings
            ]
        }

    @classmethod
    async def from_dict(cls, data: Dict[str, Any]) -> 'CBM':
        """Create CBM from dictionary"""
        cbm = cls(data['name'])
        
        # Recreate models
        for model_name, model_data in data['models'].items():
            model = Model(
                name=model_data['name'],
                provider=model_data['provider']
            )
            model.role = model_data['role']
            
            # Get bindings for this model
            model_bindings = []
            for b in data['bindings']:
                if b['source'] == model.name:
                    adhesive_type = AdhesiveType[b['type']]
                    if adhesive_type == AdhesiveType.TAPE:
                        config = BindingConfig.tape(
                            b['source'],
                            b['target'],
                            timedelta(seconds=b['properties'].get('duration', 1800))
                        )
                    elif adhesive_type == AdhesiveType.VELCRO:
                        config = BindingConfig.velcro(
                            b['source'],
                            b['target'],
                            b['properties'].get('reconnect_attempts', 3)
                        )
                    elif adhesive_type == AdhesiveType.GLUE:
                        config = BindingConfig.glue(
                            b['source'],
                            b['target'],
                            b['properties'].get('strength', 1.0)
                        )
                    elif adhesive_type == AdhesiveType.MAGNET:
                        config = BindingConfig.magnet(
                            b['source'],
                            b['target'],
                            b['properties'].get('polarity', 'attract')
                        )
                    model_bindings.append(config)
            
            await cbm.add_model(model, model_bindings)
        
        return cbm
