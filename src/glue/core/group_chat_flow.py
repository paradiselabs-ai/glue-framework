"""GLUE Group Chat Flow System"""

import asyncio
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from .model import Model
from .conversation import ConversationManager
from .memory import MemoryManager
from .context import ContextState, InteractionType
from ..magnetic.field import MagneticField, ResourceState
from ..tools.magnetic import MagneticTool
from .logger import get_logger
from ..core.adhesive import AdhesiveType
from ..magnetic.rules import InteractionPattern

class ConversationState(Enum):
    """States a conversation can be in"""
    IDLE = auto()
    ACTIVE = auto()
    CHATTING = auto()  # Bidirectional chat (><)
    PUSHING = auto()   # One-way push (->)
    PULLING = auto()   # One-way pull (<-)
    COMPLETE = auto()

@dataclass
class ConversationGroup:
    """Group of models in a conversation"""
    models: Set[str]
    state: ConversationState = ConversationState.IDLE
    context: Optional[ContextState] = None
    shared_tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # tool -> {relationship, binding_type}
    last_active: Optional[datetime] = None
    resource_pool: Dict[str, Any] = field(default_factory=dict)  # Persistent tool data

class GroupChatManager:
    """
    Manages model-to-model chat and tool interactions.
    
    Features:
    - Model interaction patterns (><, ->, <-, <>)
    - Tool sharing with persistence
    - Context-aware state management
    - Resource pooling
    """
    
    # Valid interaction patterns
    VALID_PATTERNS = {
        "><": InteractionPattern.ATTRACT,
        "->": InteractionPattern.PUSH,
        "<-": InteractionPattern.PULL,
        "<>": InteractionPattern.REPEL
    }
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.models: Dict[str, Model] = {}
        self.conversation_manager = ConversationManager()
        self.memory_manager = MemoryManager()
        
        # Conversation tracking
        self.active_conversations: Dict[str, ConversationGroup] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        
        # Tool management
        self.tools: Dict[str, MagneticTool] = {}
        self.tool_relationships: Dict[str, Dict[str, Dict[str, Any]]] = {}  # model -> {tool -> {relationship, binding}}
        
        # Initialize registry with state manager
        from .state import StateManager
        from .registry import ResourceRegistry
        self._registry = ResourceRegistry(StateManager())
        
        # Magnetic field for interactions
        self.field = MagneticField(name, self._registry)
    
    async def add_model(self, model: Model) -> None:
        """Add a model to the chat system"""
        self.logger.debug(f"Adding model: {model.name}")
        self.models[model.name] = model
        self.tool_relationships[model.name] = {}
        await self.field.add_resource(model)
    
    async def add_tool(self, tool: MagneticTool) -> None:
        """Add a tool to the system"""
        self.logger.debug(f"Adding tool: {tool.name}")
        self.tools[tool.name] = tool
        await self.field.add_resource(tool)
    
    async def set_tool_relationship(
        self,
        model_name: str,
        tool_name: str,
        relationship: str,  # "><", "->", "<-", or "<>"
        binding_type: AdhesiveType = AdhesiveType.VELCRO
    ) -> None:
        """
        Set relationship between model and tool
        
        Args:
            model_name: Name of the model
            tool_name: Name of the tool
            relationship: Interaction pattern
            binding_type: Adhesive binding type for persistence
        """
        self.logger.debug(f"Setting {relationship} relationship between {model_name} and {tool_name}")
        
        # Validate inputs
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")
        if relationship not in self.VALID_PATTERNS:
            raise ValueError(f"Invalid relationship pattern: {relationship}")
            
        # Store relationship
        self.tool_relationships[model_name][tool_name] = {
            'relationship': relationship,
            'binding': binding_type,
            'pattern': self.VALID_PATTERNS[relationship]
        }
        
        # Update magnetic field
        model = self.models[model_name]
        tool = self.tools[tool_name]
        
        try:
            if relationship == "><":
                await self.field.attract(model, tool)
            elif relationship == "->":
                await self.field.enable_push(model, tool)
            elif relationship == "<-":
                await self.field.enable_pull(model, tool)
            elif relationship == "<>":
                await self.field.repel(model, tool)
        except Exception as e:
            self.logger.error(f"Error setting relationship: {str(e)}")
            # Clean up partial relationship
            if tool_name in self.tool_relationships[model_name]:
                del self.tool_relationships[model_name][tool_name]
            raise
    
    async def start_chat(
        self,
        model1: str,
        model2: str,
        context: Optional[ContextState] = None
    ) -> str:
        """Start a bidirectional chat between models"""
        self.logger.debug(f"Starting chat between {model1} and {model2}")
        
        if model1 not in self.models or model2 not in self.models:
            raise ValueError("Both models must be in the system")
        
        # Generate conversation ID
        conv_id = f"chat_{len(self.active_conversations)}_{datetime.now().timestamp()}"
        
        try:
            # Create conversation group with resource pool
            group = ConversationGroup(
                models={model1, model2},
                state=ConversationState.CHATTING,
                context=context,
                last_active=datetime.now(),
                resource_pool={}  # Initialize empty resource pool
            )
            
            # Enable chat in magnetic field
            await self.field.enable_chat(
                self.models[model1],
                self.models[model2]
            )
            
            # Add to active conversations
            self.active_conversations[conv_id] = group
            
            self.logger.info(f"Started chat {conv_id} between {model1} and {model2}")
            return conv_id
            
        except Exception as e:
            self.logger.error(f"Error starting chat: {str(e)}")
            # Clean up if needed
            if conv_id in self.active_conversations:
                await self.end_chat(conv_id)
            raise
    
    def _get_tool_instance(
        self,
        tool_name: str,
        model_name: str,
        conversation_id: str
    ) -> MagneticTool:
        """Get appropriate tool instance based on binding type"""
        self.logger.debug(f"Getting tool instance for {tool_name} (model: {model_name})")
        
        group = self.active_conversations[conversation_id]
        relationship = self.tool_relationships[model_name][tool_name]
        binding_type = relationship['binding']
        
        try:
            if binding_type == AdhesiveType.GLUE:
                # Full persistence - use shared instance
                if tool_name not in group.resource_pool:
                    self.logger.debug(f"Creating new shared instance for {tool_name}")
                    group.resource_pool[tool_name] = self.tools[tool_name].create_instance()
                return group.resource_pool[tool_name]
                
            elif binding_type == AdhesiveType.VELCRO:
                # Session persistence - use conversation-scoped instance
                key = f"{model_name}_{tool_name}"
                if key not in group.resource_pool:
                    self.logger.debug(f"Creating new session instance for {tool_name}")
                    group.resource_pool[key] = self.tools[tool_name].create_instance()
                return group.resource_pool[key]
                
            else:  # TAPE
                # No persistence - create new instance
                self.logger.debug(f"Creating new isolated instance for {tool_name}")
                return self.tools[tool_name].create_isolated_instance()
                
        except Exception as e:
            self.logger.error(f"Error creating tool instance: {str(e)}")
            raise
    
    async def process_message(
        self,
        conversation_id: str,
        content: str,
        from_model: Optional[str] = None,
        target_model: Optional[str] = None
    ) -> str:
        """Process a message in a conversation"""
        self.logger.debug(f"Processing message in conversation {conversation_id}")
        
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        group = self.active_conversations[conversation_id]
        
        try:
            # Update context if needed
            if group.context:
                await self.field.update_context(group.context)
            
            # Get available tools based on relationships and bindings
            available_tools = {}
            for model_name in group.models:
                model_tools = self.tool_relationships.get(model_name, {})
                for tool_name, config in model_tools.items():
                    if config['relationship'] in ["><", "->", "<-"]:
                        available_tools[tool_name] = self._get_tool_instance(
                            tool_name,
                            model_name,
                            conversation_id
                        )
            
            # Process through conversation manager
            response = await self.conversation_manager.process(
                models={name: self.models[name] for name in group.models},
                binding_patterns={'field': self.field},
                user_input=content,
                tools=available_tools,
                context=group.context
            )
            
            # Store in history
            self.conversation_history.append({
                'conversation_id': conversation_id,
                'timestamp': datetime.now().isoformat(),
                'from_model': from_model,
                'target_model': target_model,
                'content': content,
                'response': response
            })
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            raise
    
    async def end_chat(self, conversation_id: str) -> None:
        """End a chat conversation"""
        self.logger.debug(f"Ending conversation {conversation_id}")
        
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        group = self.active_conversations[conversation_id]
        
        try:
            # Clean up magnetic field
            for model_name in group.models:
                model = self.models[model_name]
                # Reset model state
                if model._state in [ResourceState.CHATTING, ResourceState.PULLING]:
                    model._state = ResourceState.IDLE
            
            # Clean up non-persistent tools
            for tool_name, instance in group.resource_pool.items():
                if '_' in tool_name:  # Model-specific instances
                    model_name = tool_name.split('_')[0]
                    if model_name in self.tool_relationships:
                        relationship = self.tool_relationships[model_name].get(tool_name.split('_')[1])
                        if relationship and relationship['binding'] != AdhesiveType.GLUE:
                            if hasattr(instance, 'cleanup'):
                                self.logger.debug(f"Cleaning up tool instance: {tool_name}")
                                await instance.cleanup()
            
            # Mark conversation complete
            group.state = ConversationState.COMPLETE
            
            # Remove from active conversations
            del self.active_conversations[conversation_id]
            
        except Exception as e:
            self.logger.error(f"Error ending conversation: {str(e)}")
            raise
    
    def get_active_conversations(self) -> Dict[str, ConversationGroup]:
        """Get all active conversations"""
        return {
            conv_id: group 
            for conv_id, group in self.active_conversations.items()
            if group.state != ConversationState.COMPLETE
        }
    
    def get_conversation_tools(
        self,
        conversation_id: str,
        model_name: str
    ) -> Dict[str, MagneticTool]:
        """Get tools available to a model in a conversation"""
        self.logger.debug(f"Getting tools for {model_name} in conversation {conversation_id}")
        
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
            
        tools = {}
        model_tools = self.tool_relationships.get(model_name, {})
        for tool_name, config in model_tools.items():
            if config['relationship'] in ["><", "->", "<-"]:
                tools[tool_name] = self._get_tool_instance(
                    tool_name,
                    model_name,
                    conversation_id
                )
        return tools

    async def cleanup(self) -> None:
        """Clean up resources"""
        self.logger.debug("Cleaning up resources")
        try:
            # End all conversations
            for conv_id in list(self.active_conversations.keys()):
                await self.end_chat(conv_id)
            
            # Clean up tools
            for tool in self.tools.values():
                if hasattr(tool, 'cleanup'):
                    await tool.cleanup()
            
            # Clean up field
            await self.field.cleanup()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            raise
