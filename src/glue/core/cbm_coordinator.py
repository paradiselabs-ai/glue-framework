# src/glue/core/cbm_orchestrator.py

"""CBM Internal Orchestration System"""

import asyncio
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from .model import Model
from .conversation import ConversationManager
from .memory import MemoryManager
from .context import ContextState
from ..magnetic.field import MagneticField
from .logger import get_logger

class ModelState(Enum):
    """States a model can be in within a CBM"""
    IDLE = auto()
    PROCESSING = auto()
    WAITING = auto()
    COMPLETE = auto()

@dataclass
class ModelContext:
    """Context for a model within the CBM"""
    state: ModelState = ModelState.IDLE
    last_output: Optional[str] = None
    dependencies: Set[str] = field(default_factory=set)
    waiting_for: Set[str] = field(default_factory=set)

class CBMOrchestrator:
    """Manages internal CBM operations and model interactions"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.models: Dict[str, Model] = {}
        self.conversation_manager = ConversationManager()
        self.memory_manager = MemoryManager()
        
        # Model tracking
        self.model_contexts: Dict[str, ModelContext] = {}
        self.model_dependencies: Dict[str, Set[str]] = {}
        
        # Initialize registry with state manager
        from .state import StateManager
        from .registry import ResourceRegistry
        self._registry = ResourceRegistry(StateManager())
        
        # Internal magnetic field for model interactions
        self.field = MagneticField(f"{name}_internal", self._registry)
        
        # Response synthesis
        self.synthesis_queue: List[Dict[str, Any]] = []
    
    async def add_model(self, model: Model) -> None:
        """Add a model to the CBM"""
        self.models[model.name] = model
        self.model_contexts[model.name] = ModelContext()
        self.model_dependencies[model.name] = set()
        await self.field.add_resource(model)
    
    def add_dependency(self, model: str, depends_on: str) -> None:
        """Add a dependency between models"""
        if model not in self.models or depends_on not in self.models:
            raise ValueError("Both models must be in the CBM")
        self.model_dependencies[model].add(depends_on)
    
    async def _process_model(
        self,
        model_name: str,
        input_data: str,
        context: Optional[ContextState] = None
    ) -> Optional[str]:
        """Process input through a single model"""
        model = self.models[model_name]
        model_context = self.model_contexts[model_name]
        
        # Check dependencies
        dependencies = self.model_dependencies[model_name]
        if dependencies:
            waiting_for = {
                dep for dep in dependencies
                if self.model_contexts[dep].state != ModelState.COMPLETE
            }
            if waiting_for:
                model_context.state = ModelState.WAITING
                model_context.waiting_for = waiting_for
                return None
        
        # Process input
        model_context.state = ModelState.PROCESSING
        response = await self.conversation_manager.process(
            models={model_name: model},
            binding_patterns={'field': self.field},
            user_input=input_data
        )
        
        # Update context
        model_context.state = ModelState.COMPLETE
        model_context.last_output = response
        
        # Add to synthesis queue
        self.synthesis_queue.append({
            'model': model_name,
            'output': response,
            'timestamp': datetime.now()
        })
        
        return response
    
    def _synthesize_responses(self) -> str:
        """Synthesize multiple model outputs into a single response"""
        if not self.synthesis_queue:
            return ""
        
        # Sort by timestamp
        sorted_responses = sorted(
            self.synthesis_queue,
            key=lambda x: x['timestamp']
        )
        
        # Combine responses, maintaining conversation flow
        synthesized = []
        for response in sorted_responses:
            model_name = response['model']
            output = response['output']
            
            # Skip redundant or superseded information
            if any(
                prev_output in output
                for prev in synthesized
                for prev_output in prev.split('\n')
            ):
                continue
            
            synthesized.append(output)
        
        return "\n\n".join(synthesized)
    
    async def process(
        self,
        input_data: str,
        context: Optional[ContextState] = None
    ) -> str:
        """Process input through the CBM"""
        # Reset states
        for context in self.model_contexts.values():
            context.state = ModelState.IDLE
            context.last_output = None
            context.waiting_for.clear()
        self.synthesis_queue.clear()
        
        # Update field context
        if context:
            await self.field.update_context(context)
        
        # Process through each model
        tasks = []
        for model_name in self.models:
            task = asyncio.create_task(
                self._process_model(model_name, input_data, context)
            )
            tasks.append(task)
        
        # Wait for all models to complete
        await asyncio.gather(*tasks)
        
        # Synthesize responses
        return self._synthesize_responses()
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        await self.field.cleanup()
        self.synthesis_queue.clear()
        for context in self.model_contexts.values():
            context.state = ModelState.IDLE
            context.last_output = None
            context.waiting_for.clear()
