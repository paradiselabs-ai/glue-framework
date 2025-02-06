"""GLUE Group Chat System"""

import asyncio
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from .model import Model
from .conversation import ConversationManager
from .state import ResourceState
from .types import AdhesiveType
from .logger import get_logger
from .context import ContextState

@dataclass
class ChatGroup:
    """Group of models in a chat"""
    models: Set[str]
    state: ResourceState = ResourceState.IDLE
    context: Optional[ContextState] = None
    tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_active: Optional[datetime] = None
    resource_pool: Dict[str, Any] = field(default_factory=dict)

class GroupChatManager:
    """
    Manages model-to-model chat within teams.
    
    Features:
    - Free-flowing model-to-model communication
      * Models in a team can chat directly
      * No magnetic field restrictions within teams
      * Context-aware conversations
    
    - Tool Management
      * Adhesive-based tool bindings (GLUE/VELCRO/TAPE)
      * Tool instance lifecycle management
      * Resource pooling with persistence options
    
    - State Management
      * Clean conversation tracking
      * History with context preservation
      * Proper resource cleanup
    
    Note: For team-to-team communication, use TeamCommunicationManager.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger()
        
        # Core components
        self.models: Dict[str, Model] = {}
        self.conversation_manager = ConversationManager(sticky=True)  # Enable persistence
        
        # Chat tracking
        self.active_chats: Dict[str, ChatGroup] = {}
        self.chat_history: List[Dict[str, Any]] = []
        
        # Tool management
        self.tools: Dict[str, Any] = {}
        self.tool_bindings: Dict[str, Dict[str, AdhesiveType]] = {}
    
    def add_model(self, model: Model) -> None:
        """Add a model to the chat system"""
        self.logger.debug(f"Adding model: {model.name}")
        self.models[model.name] = model
        self.tool_bindings[model.name] = {}
    
    async def add_tool(self, tool: Any) -> None:
        """Add a tool to the system"""
        self.logger.debug(f"Adding tool: {tool.name}")
        self.tools[tool.name] = tool
    
    async def bind_tool(
        self,
        model_name: str,
        tool_name: str,
        binding_type: AdhesiveType = AdhesiveType.VELCRO
    ) -> None:
        """Bind a tool to a model with adhesive type"""
        self.logger.debug(f"Binding {tool_name} to {model_name}")
        
        # Validate inputs
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")
            
        # Store binding
        self.tool_bindings[model_name][tool_name] = binding_type
    
    async def start_chat(
        self,
        model1: str,
        model2: str,
        context: Optional[ContextState] = None
    ) -> str:
        """Start a chat between models"""
        self.logger.debug(f"Starting chat between {model1} and {model2}")
        
        if model1 not in self.models or model2 not in self.models:
            raise ValueError("Both models must be in the system")
        
        # Generate chat ID
        chat_id = f"chat_{len(self.active_chats)}_{datetime.now().timestamp()}"
        
        try:
            # Create chat group
            group = ChatGroup(
                models={model1, model2},
                state=ResourceState.ACTIVE,
                context=context,
                last_active=datetime.now()
            )
            
            # Add to active chats
            self.active_chats[chat_id] = group
            
            self.logger.info(f"Started chat {chat_id} between {model1} and {model2}")
            return chat_id
            
        except Exception as e:
            self.logger.error(f"Error starting chat: {str(e)}")
            # Clean up if needed
            if chat_id in self.active_chats:
                await self.end_chat(chat_id)
            raise
    
    def _get_tool_instance(
        self,
        tool_name: str,
        model_name: str,
        chat_id: str
    ) -> Any:
        """
        Get appropriate tool instance based on binding type and persistence level.
        
        Args:
            tool_name: Name of tool to instantiate
            model_name: Name of model requesting the tool
            chat_id: ID of current chat session
            
        Returns:
            Tool instance with appropriate persistence:
            - GLUE: Returns shared instance from group resource pool
            - VELCRO: Returns chat-scoped instance for the model
            - TAPE: Returns new isolated instance
            
        The instance lifecycle follows adhesive rules:
        - GLUE instances persist across all chat sessions
        - VELCRO instances persist for the chat session
        - TAPE instances are created new each time
        """
        self.logger.debug(f"Getting tool instance for {tool_name} (model: {model_name})")
        
        group = self.active_chats[chat_id]
        binding_type = self.tool_bindings[model_name][tool_name]
        
        try:
            if binding_type == AdhesiveType.GLUE:
                # Full persistence - use shared instance
                if tool_name not in group.resource_pool:
                    self.logger.debug(f"Creating new shared instance for {tool_name}")
                    group.resource_pool[tool_name] = self.tools[tool_name].create_instance()
                return group.resource_pool[tool_name]
                
            elif binding_type == AdhesiveType.VELCRO:
                # Session persistence - use chat-scoped instance
                key = f"{model_name}_{tool_name}"
                if key not in group.resource_pool:
                    self.logger.debug(f"Creating new session instance for {tool_name}")
                    group.resource_pool[key] = self.tools[tool_name].create_instance()
                return group.resource_pool[key]
                
            else:  # TAPE
                # No persistence - create new instance
                self.logger.debug(f"Creating new isolated instance for {tool_name}")
                return self.tools[tool_name].create_instance()
                
        except Exception as e:
            self.logger.error(f"Error creating tool instance: {str(e)}")
            raise
    
    async def process_message(
        self,
        chat_id: str,
        content: str,
        from_model: Optional[str] = None,
        target_model: Optional[str] = None
    ) -> str:
        """
        Process a message in a chat with tool access and context preservation.
        
        This method:
        1. Validates the chat exists and is active
        2. Gathers available tools based on model bindings:
           - Respects adhesive types (GLUE/VELCRO/TAPE)
           - Creates appropriate tool instances
           - Manages tool lifecycle
        3. Processes message through conversation manager:
           - Maintains chat context
           - Handles tool usage
           - Preserves conversation flow
        4. Stores history with full context
        
        Args:
            chat_id: ID of chat to process message in
            content: Message content to process
            from_model: Optional sender model name
            target_model: Optional target model name
            
        Returns:
            Processed response from the conversation
            
        The processing respects tool bindings and persistence:
        - GLUE tools maintain state across all messages
        - VELCRO tools maintain state within the chat
        - TAPE tools are fresh for each message
        """
        self.logger.debug(f"Processing message in chat {chat_id}")
        
        if chat_id not in self.active_chats:
            raise ValueError(f"Chat {chat_id} not found")
            
        group = self.active_chats[chat_id]
        
        try:
            # Get available tools based on bindings
            available_tools = {}
            for model_name in group.models:
                model_tools = self.tool_bindings.get(model_name, {})
                for tool_name, binding_type in model_tools.items():
                    available_tools[tool_name] = self._get_tool_instance(
                        tool_name,
                        model_name,
                        chat_id
                    )
            
            # Log message routing
            self.logger.info(f"\n{'='*20} Model Communication {'='*20}")
            self.logger.info(f"Chat: {chat_id}")
            self.logger.info(f"From: {from_model or 'system'}")
            self.logger.info(f"To: {target_model or 'all models'}")
            self.logger.info(f"Models in chat: {', '.join(group.models)}")
            self.logger.info(f"Available tools: {list(available_tools.keys())}")
            
            # Process through conversation manager with context
            response = await self.conversation_manager.process(
                models={name: self.models[name] for name in group.models},
                user_input=content,
                tools=available_tools,
                context=group.context
            )
            
            # Log tool usage and context
            if group.context and group.context.tools_required:
                self.logger.info(f"\nTool Usage:")
                for tool in group.context.tools_required:
                    binding = next(
                        (binding for model, bindings in self.tool_bindings.items()
                         for t, binding in bindings.items() if t == tool),
                        None
                    )
                    self.logger.info(f"- {tool} (binding: {binding.name if binding else 'none'})")
            
            # Store in history with context
            history_entry = {
                'chat_id': chat_id,
                'timestamp': datetime.now().isoformat(),
                'from_model': from_model,
                'target_model': target_model,
                'content': content,
                'response': response,
                'context': group.context
            }
            self.chat_history.append(history_entry)
            
            # Log collaboration result
            self.logger.info(f"\nCollaboration Result:")
            self.logger.info(f"Message processed successfully")
            self.logger.info(f"Response length: {len(response)}")
            self.logger.info(f"{'='*50}\n")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            raise
    
    async def end_chat(self, chat_id: str) -> None:
        """End a chat"""
        self.logger.debug(f"Ending chat {chat_id}")
        
        if chat_id not in self.active_chats:
            raise ValueError(f"Chat {chat_id} not found")
            
        group = self.active_chats[chat_id]
        
        try:
            # Clean up non-persistent tools
            for tool_name, instance in group.resource_pool.items():
                if '_' in tool_name:  # Model-specific instances
                    model_name = tool_name.split('_')[0]
                    if model_name in self.tool_bindings:
                        binding_type = self.tool_bindings[model_name].get(tool_name.split('_')[1])
                        if binding_type != AdhesiveType.GLUE:
                            if hasattr(instance, 'cleanup'):
                                self.logger.debug(f"Cleaning up tool instance: {tool_name}")
                                await instance.cleanup()
            
            # Set state to IDLE
            group.state = ResourceState.IDLE
            
            # Remove from active chats
            del self.active_chats[chat_id]
            
        except Exception as e:
            self.logger.error(f"Error ending chat: {str(e)}")
            raise
    
    def get_active_chats(self) -> Dict[str, ChatGroup]:
        """Get all active chats"""
        return {
            chat_id: group 
            for chat_id, group in self.active_chats.items()
            if group.state == ResourceState.ACTIVE
        }
    
    def get_chat_tools(
        self,
        chat_id: str,
        model_name: str
    ) -> Dict[str, Any]:
        """Get tools available to a model in a chat"""
        self.logger.debug(f"Getting tools for {model_name} in chat {chat_id}")
        
        if chat_id not in self.active_chats:
            raise ValueError(f"Chat {chat_id} not found")
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
            
        tools = {}
        model_tools = self.tool_bindings.get(model_name, {})
        for tool_name, binding_type in model_tools.items():
            tools[tool_name] = self._get_tool_instance(
                tool_name,
                model_name,
                chat_id
            )
        return tools

    async def cleanup(self) -> None:
        """Clean up resources"""
        self.logger.debug("Cleaning up resources")
        try:
            # End all chats
            for chat_id in list(self.active_chats.keys()):
                await self.end_chat(chat_id)
            
            # Clean up tools
            for tool in self.tools.values():
                if hasattr(tool, 'cleanup'):
                    await tool.cleanup()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            raise
