"""CBM Orchestrator Implementation"""

from typing import Dict, Optional, Set, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from .model import Model
from .context import ContextState
from .logger import get_logger
from .memory import MemoryManager
from .binding import Binding, BindingConfig

@dataclass
class OrchestratorState:
    """State tracking for orchestrator"""
    models: Dict[str, Model] = field(default_factory=dict)
    bindings: List[Binding] = field(default_factory=list)
    last_execution: Optional[datetime] = None
    error_count: int = 0
    memory: Dict[str, Any] = field(default_factory=dict)

class CBMOrchestrator:
    """
    Orchestrates interactions between models in a CBM.
    
    Features:
    - Type-safe binding system
    - Error handling and propagation
    - State management
    - Memory integration
    - Dependency tracking
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.state = OrchestratorState()
        self.memory_manager = MemoryManager()
        
        # Dependency tracking
        self.dependencies: Dict[str, Set[str]] = {}  # model -> depends_on
        self.reverse_deps: Dict[str, Set[str]] = {}  # model -> depended_by
        
        # Error handling
        self._error_handlers: Dict[str, List[callable]] = {}
        self._state_handlers: Dict[str, List[callable]] = {}
        
    async def add_model(self, model: Model, bindings: Optional[List[BindingConfig]] = None) -> None:
        """
        Add a model to the orchestrator with optional bindings
        
        Args:
            model: Model to add
            bindings: Optional binding configurations
        """
        self.state.models[model.name] = model
        
        # Setup dependency tracking
        if model.name not in self.dependencies:
            self.dependencies[model.name] = set()
        if model.name not in self.reverse_deps:
            self.reverse_deps[model.name] = set()
            
        # Setup bindings if provided
        if bindings:
            for config in bindings:
                binding = Binding(config)
                self.state.bindings.append(binding)
                binding.on('error', lambda e: self._handle_binding_error(model.name, e))
            
    def add_dependency(self, model: str, depends_on: str) -> None:
        """
        Add a dependency between models
        
        Args:
            model: Name of dependent model
            depends_on: Name of model being depended on
            
        Raises:
            ValueError: If models don't exist or would create cycle
        """
        if model not in self.state.models or depends_on not in self.state.models:
            raise ValueError("Both models must be added before creating dependency")
            
        self.dependencies[model].add(depends_on)
        self.reverse_deps[depends_on].add(model)
        
        # Check for cycles
        if self._has_cycle():
            # Remove the dependency we just added
            self.dependencies[model].remove(depends_on)
            self.reverse_deps[depends_on].remove(model)
            raise ValueError("Adding this dependency would create a cycle")
            
    def _has_cycle(self) -> bool:
        """Check if dependency graph has cycles using DFS"""
        visited = set()
        path = set()
        
        def visit(node: str) -> bool:
            if node in path:
                return True  # Found cycle
            if node in visited:
                return False
                
            path.add(node)
            visited.add(node)
            
            # Check all dependencies
            for dep in self.dependencies[node]:
                if visit(dep):
                    return True
                    
            path.remove(node)
            return False
            
        # Check from each node
        for node in self.models:
            if node not in visited:
                if visit(node):
                    return True
        return False
        
    def _get_execution_order(self) -> list[str]:
        """Get topological sort of models based on dependencies"""
        visited = set()
        temp = set()  # For cycle detection
        order = []
        
        def visit(node: str) -> None:
            if node in temp:
                raise ValueError("Cycle detected in dependencies")
            if node in visited:
                return
                
            temp.add(node)
            
            # Visit all dependencies first
            for dep in self.dependencies[node]:
                visit(dep)
                
            temp.remove(node)
            visited.add(node)
            order.append(node)
            
        # Visit all nodes
        for node in self.models:
            if node not in visited:
                visit(node)
                
        return order
        
    async def process(
        self,
        user_input: str,
        context: Optional[ContextState] = None
    ) -> str:
        """
        Process input through models in dependency order.
        
        Features:
        - State tracking
        - Error handling
        - Memory integration
        - Event propagation
        
        Args:
            user_input: Input to process
            context: Optional context
            
        Returns:
            Final synthesized response
            
        Raises:
            OrchestratorError: On processing failure
        """
        self.logger.debug(f"Orchestrator {self.name} processing input")
        
        try:
            # Update state
            self.state.last_execution = datetime.now()
            
            # Get execution order
            order = self._get_execution_order()
            
            # Process through models
            current_input = user_input
            responses = {}
            
            for model_name in order:
                model = self.state.models[model_name]
                
                # Get responses from dependencies
                dep_responses = []
                for dep in self.dependencies[model_name]:
                    if dep in responses:
                        dep_responses.append(responses[dep])
                
                # Store in memory before processing
                self.memory_manager.store(
                    key=f"{model_name}_input_{datetime.now().timestamp()}",
                    content=current_input
                )
                
                # Process through model
                try:
                    response = await model.process(
                        current_input,
                        context=context,
                        dependency_outputs=dep_responses
                    )
                    responses[model_name] = response
                    current_input = response
                    
                    # Store successful response
                    self.memory_manager.store(
                        key=f"{model_name}_output_{datetime.now().timestamp()}",
                        content=response
                    )
                    
                except Exception as e:
                    self.state.error_count += 1
                    self._emit_error(model_name, e)
                    raise OrchestratorError(f"Error in model {model_name}: {str(e)}")
            
            # Store final state
            self.state.memory['last_responses'] = responses
            
            return responses[order[-1]]
            
        except Exception as e:
            self.state.error_count += 1
            self._emit_error('orchestrator', e)
            raise
        
    def on_error(self, handler: callable) -> None:
        """Register error handler"""
        if 'error' not in self._error_handlers:
            self._error_handlers['error'] = []
        self._error_handlers['error'].append(handler)
    
    def on_state_change(self, handler: callable) -> None:
        """Register state change handler"""
        if 'state' not in self._state_handlers:
            self._state_handlers['state'] = []
        self._state_handlers['state'].append(handler)
    
    def _emit_error(self, source: str, error: Exception) -> None:
        """Emit error to handlers"""
        if 'error' in self._error_handlers:
            for handler in self._error_handlers['error']:
                handler(source, error)
    
    def _handle_binding_error(self, model: str, error: Exception) -> None:
        """Handle binding-specific errors"""
        self.logger.error(f"Binding error for model {model}: {error}")
        self._emit_error(f"binding_{model}", error)
    
    async def cleanup(self) -> None:
        """Clean up orchestrator resources"""
        # Clean up models
        for model in self.state.models.values():
            await model.cleanup()
            
        # Clean up bindings
        for binding in self.state.bindings:
            binding.destroy()
            
        # Clear state
        self.state = OrchestratorState()
        
        # Clear memory
        self.memory_manager.clear()

class OrchestratorError(Exception):
    """Base class for orchestrator errors"""
    pass
