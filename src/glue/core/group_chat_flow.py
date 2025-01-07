# src/glue/core/group_chat_flow.py

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

class ConversationState(Enum):
    """States a conversation can be in"""
    IDLE = auto()
    ACTIVE = auto()
    CHATTING = auto()  # Special state for <--> chat
    COMPLETE = auto()

@dataclass
class ConversationGroup:
    """Group of models in a conversation"""
    models: Set[str]
    state: ConversationState = ConversationState.IDLE
    context: Optional[ContextState] = None
    shared_tools: Dict[str, str] = field(default_factory=dict)  # tool -> relationship type
    last_active: Optional[datetime] = None

class GroupChatManager:
    """Manages model-to-model chat and tool interactions"""
    
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
        self.tool_relationships: Dict[str, Dict[str, str]] = {}  # model -> {tool -> relationship}
        
        # Initialize registry with state manager
        from .state import StateManager
        from .registry import ResourceRegistry
        self._registry = ResourceRegistry(StateManager())
        
        # Magnetic field for interactions
        self.field = MagneticField(name, self._registry)
    
    async def add_model(self, model: Model) -> None:
        """Add a model to the chat system"""
        self.models[model.name] = model
        self.tool_relationships[model.name] = {}
        await self.field.add_resource(model)
    
    async def add_tool(self, tool: MagneticTool) -> None:
        """Add a tool to the system"""
        self.tools[tool.name] = tool
        await self.field.add_resource(tool)
    
    async def set_tool_relationship(
        self,
        model_name: str,
        tool_name: str,
        relationship: str  # "><", "<-", or "<>"
    ) -> None:
        """Set relationship between model and tool"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")
            
        self.tool_relationships[model_name][tool_name] = relationship
        
        # Update magnetic field
        model = self.models[model_name]
        tool = self.tools[tool_name]
        
        if relationship == "><":
            await self.field.attract(model, tool)
        elif relationship == "<-":
            await self.field.enable_pull(model, tool)
        elif relationship == "<>":
            await self.field.repel(model, tool)
    
    async def start_chat(
        self,
        model1: str,
        model2: str,
        context: Optional[ContextState] = None
    ) -> str:
        """Start a bidirectional chat between models"""
        if model1 not in self.models or model2 not in self.models:
            raise ValueError("Both models must be in the system")
        
        # Generate conversation ID
        conv_id = f"chat_{len(self.active_conversations)}_{datetime.now().timestamp()}"
        
        # Create conversation group
        group = ConversationGroup(
            models={model1, model2},
            state=ConversationState.CHATTING,
            context=context,
            last_active=datetime.now()
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
    
    async def process_message(
        self,
        conversation_id: str,
        content: str,
        from_model: Optional[str] = None,
        target_model: Optional[str] = None
    ) -> str:
        """Process a message in a conversation"""
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        group = self.active_conversations[conversation_id]
        
        # Update context if needed
        if group.context:
            await self.field.update_context(group.context)
        
        # Get available tools based on relationships
        available_tools = {}
        for model_name in group.models:
            model_tools = self.tool_relationships.get(model_name, {})
            for tool_name, relationship in model_tools.items():
                if relationship in ["><", "<-"]:  # Can use or receive from tool
                    available_tools[tool_name] = self.tools[tool_name]
        
        # Process through conversation manager
        response = await self.conversation_manager.process(
            models={name: self.models[name] for name in group.models},
            binding_patterns={'field': self.field},
            user_input=content,
            tools=available_tools
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
    
    async def end_chat(self, conversation_id: str) -> None:
        """End a chat conversation"""
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        group = self.active_conversations[conversation_id]
        
        # Clean up magnetic field
        for model_name in group.models:
            model = self.models[model_name]
            # Reset model state
            if model._state == ResourceState.CHATTING:
                model._state = ResourceState.IDLE
        
        # Mark conversation complete
        group.state = ConversationState.COMPLETE
        
        # Remove from active conversations
        del self.active_conversations[conversation_id]
    
    def get_active_conversations(self) -> Dict[str, ConversationGroup]:
        """Get all active conversations"""
        return {
            conv_id: group 
            for conv_id, group in self.active_conversations.items()
            if group.state != ConversationState.COMPLETE
        }

    async def cleanup(self) -> None:
        """Clean up resources"""
        # End all conversations
        for conv_id in list(self.active_conversations.keys()):
            await self.end_chat(conv_id)
        
        # Clean up tools
        for tool in self.tools.values():
            if hasattr(tool, 'cleanup'):
                await tool.cleanup()
        
        # Clean up field
        await self.field.cleanup()
