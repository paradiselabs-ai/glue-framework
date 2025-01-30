"""GLUE Conversation Manager

Core component for facilitating natural, efficient conversations between models.
Handles conversation flow, context management, tool usage, and memory within teams.
"""

import os
import json
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from pathlib import Path

from .model import Model
from .memory import MemoryManager
from .logger import get_logger
from .context import ContextAnalyzer, ContextState, ComplexityLevel
from .role import DynamicRole, RoleState
from ..tools.chain import ToolChainOptimizer
from .types import AdhesiveType

class ConversationManager:
    """
    Manages natural and efficient conversations between models within a team.
    
    Core Features:
    - Natural Conversation Flow
      * Context-aware message formatting
      * Turn management and coordination
      * Free-flowing intra-team communication
    
    - Tool Integration
      * Smart tool chain optimization
      * Persistence management (GLUE/VELCRO/TAPE)
      * Usage tracking and performance monitoring
    
    - Memory & Context
      * Short and long-term memory
      * Context preservation
      * Role-based behavior adaptation
    
    - Error Handling
      * Graceful error recovery
      * Clear error messages
      * State preservation
    
    Team Communication:
    - Within Teams (this manager):
      * Models communicate freely
      * No magnetic field restrictions
      * Direct tool sharing and usage
      * Conversation history tracking
    
    - Between Teams (via TeamCommunicationManager):
      * Results synthesized via _synthesize_responses
      * Shared through magnetic field system
      * Follows team-to-team protocols
      * Respects magnetic operators (><, ->, <-, <>)
    
    This manager handles HOW models communicate and use tools within a team,
    while team membership and team-to-team communication are handled by
    Team and TeamCommunicationManager respectively.
    """
    
    # Tool usage patterns
    TOOL_PATTERNS = {
        r'<tool>(.*?)</tool>': lambda m: f"Use the {m.group(1)} tool",
        r'<input>(.*?)</input>': lambda m: f"with input: {m.group(1)}",
        r'<think>(.*?)</think>': lambda m: f"Reasoning: {m.group(1)}",
        r'<error>(.*?)</error>': lambda m: f"Error: {m.group(1)}"
    }
    
    def __init__(self, sticky: bool = False, workspace_dir: Optional[str] = None):
        """Initialize conversation manager"""
        self.sticky = sticky
        self.workspace_dir = os.path.abspath(workspace_dir or "workspace")
        self.history: List[Dict[str, Any]] = []
        self.active_conversation: Optional[str] = None
        
        # Core components
        self.memory_manager = MemoryManager()
        self.logger = get_logger()
        self.context_analyzer = ContextAnalyzer()
        self.tool_optimizer = ToolChainOptimizer()
        
        # Model management
        self.model_roles: Dict[str, DynamicRole] = {}
        self.model_states: Dict[str, Dict[str, Any]] = {}
        
        # Tool management
        self.tool_instances: Dict[str, Dict[str, Any]] = {}
        self.resource_pool: Dict[str, Dict[str, Any]] = {}
        self.tool_bindings: Dict[str, Dict[str, AdhesiveType]] = {}
        self.tool_usage: Dict[str, int] = {}
        
        # Performance tracking
        self.interaction_success: Dict[str, bool] = {}
        
        # Load history if sticky
        if self.sticky:
            self._load_history()
    
    def _extract_tool_usage(self, response: str) -> Optional[Tuple[str, str, str, AdhesiveType]]:
        """Extract tool name, thought, input, and adhesive type from response"""
        tool_match = re.search(r'<tool>(.*?)</tool>', response)
        input_match = re.search(r'<input>(.*?)</input>', response)
        thought_match = re.search(r'<think>(.*?)</think>', response)
        adhesive_match = re.search(r'<adhesive>(.*?)</adhesive>', response)
        
        if tool_match and input_match and adhesive_match:
            tool_name = tool_match.group(1).strip()
            tool_input = input_match.group(1).strip()
            thought = thought_match.group(1).strip() if thought_match else ""
            adhesive_str = adhesive_match.group(1).strip().upper()
            adhesive = getattr(AdhesiveType, adhesive_str)
            return (tool_name, thought, tool_input, adhesive)
            
        return None
    
    
    def _get_tool_instance(
        self,
        tool_name: str,
        conversation_id: str,
        binding_type: AdhesiveType,
        model_name: Optional[str] = None
    ) -> Any:
        """Get appropriate tool instance based on binding type"""
        if binding_type == AdhesiveType.GLUE:
            # Full persistence - use shared instance
            if tool_name not in self.resource_pool:
                self.resource_pool[tool_name] = {}
            return self.resource_pool[tool_name]
            
        elif binding_type == AdhesiveType.VELCRO:
            # Session persistence - use conversation-scoped instance
            if conversation_id not in self.tool_instances:
                self.tool_instances[conversation_id] = {}
                
            conv_instances = self.tool_instances[conversation_id]
            key = f"{model_name}_{tool_name}" if model_name else tool_name
            
            if key not in conv_instances:
                conv_instances[key] = {}
            return conv_instances[key]
            
        else:  # TAPE
            # No persistence - create new instance
            return {}
    
    async def _initialize_tool(
        self,
        tool: Any,
        binding_type: AdhesiveType,
        conversation_id: str,
        model_name: Optional[str] = None
    ) -> None:
        """Initialize tool with appropriate instance and binding"""
        # Get instance based on binding type
        instance_data = self._get_tool_instance(
            tool_name=tool.name,
            conversation_id=conversation_id,
            binding_type=binding_type,
            model_name=model_name
        )
        
        # Initialize tool
        await tool.initialize(instance_data)
        
        # Store binding type
        if model_name:
            if model_name not in self.tool_bindings:
                self.tool_bindings[model_name] = {}
            self.tool_bindings[model_name][tool.name] = binding_type
    
    async def process(
        self,
        models: Dict[str, Model],
        user_input: str,
        tools: Optional[Dict[str, Any]] = None,
        context: Optional[ContextState] = None
    ) -> str:
        """
        Process user input through models and tools within a team.
        
        This method handles the core conversation flow between models in the same team:
        - Routes messages through appropriate models
        - Manages tool usage and persistence
        - Maintains conversation history and context
        - Handles error recovery
        
        For team-to-team communication, the results from this method can be
        formatted using _synthesize_responses before being shared through
        the magnetic field system.
        
        Args:
            models: Dictionary of available models
            user_input: The input to process
            tools: Optional dictionary of available tools
            context: Optional conversation context
            
        Returns:
            The processed response or error message
        """
        try:
            self.logger.debug("Processing conversation...")
            
            # Generate conversation ID if none active
            if not self.active_conversation:
                self.active_conversation = f"conv_{datetime.now().timestamp()}"
            
            # Analyze context if not provided
            if not context:
                context = self.context_analyzer.analyze(
                    user_input,
                    available_tools=list(tools.keys()) if tools else None
                )
            self.logger.debug(f"Context: {context}")
            
            # Store user input
            message = {
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat(),
                "conversation_id": self.active_conversation
            }
            self.history.append(message)
            
            # Store in memory with context
            self.memory_manager.store(
                key=f"user_input_{message['timestamp']}",
                content=message,
                memory_type="short_term",
                context=context
            )
            
            # Initialize/update model roles with tools
            for model_name, model in models.items():
                if model_name not in self.model_roles:
                    # Get base role
                    base_role = model.role
                    
                    # Enhance with tools if available
                    if hasattr(model, "_tools"):
                        tool_names = list(model._tools.keys())
                        base_role = self._enhance_role_with_tools(base_role, tool_names)
                    
                    # Create dynamic role
                    self.model_roles[model_name] = DynamicRole(base_role)
                    
                    # Allow tools
                    if hasattr(model, "_tools"):
                        for tool_name in model._tools:
                            self.model_roles[model_name].allow_tool(tool_name)
            
            # Optimize tool chain if tools available
            optimized_tools = []
            if tools:
                tool_names = list(tools.keys())
                optimized_tools = self.tool_optimizer.optimize_chain(tool_names, context)
                self.logger.debug(f"Optimized tools: {optimized_tools}")
            
            # Process through first model
            if not models:
                return "No models available"
                
            model = next(iter(models.values()))
            current_input = user_input
            
            while True:  # Allow multiple tool uses
                # Get model context
                model_context = self._get_model_context(model.name)
                
                # Enhance input with context and complexity
                enhanced_input = self._enhance_input_with_context(
                    current_input=current_input,
                    context=model_context,
                    complexity=context.complexity if context else ComplexityLevel.SIMPLE
                )
                
                # Get model's response
                response = await model.generate(enhanced_input)
                
                # Store response
                self.history.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": self.active_conversation
                })
                
                # Check for tool usage
                tool_usage = self._extract_tool_usage(response)
                if tool_usage and tools:
                    tool_name, thought, tool_input, adhesive = tool_usage
                    
                    # Log the attempt
                    self.logger.debug(f"Tool usage detected: {tool_name}")
                    self.logger.debug(f"Thought: {thought}")
                    self.logger.debug(f"Input: {tool_input}")
                    self.logger.debug(f"Adhesive: {adhesive.name}")
                    
                    # Skip if tool not needed for simple tasks
                    if (context.complexity == ComplexityLevel.SIMPLE and
                        tool_name not in context.tools_required):
                        continue
                    
                    # Skip if optimized out
                    if tool_name not in optimized_tools:
                        continue
                    
                    # Execute tool if available
                    if tool_name in tools:
                        try:
                            tool = tools[tool_name]
                            tool_start = datetime.now()
                            # Initialize tool with binding
                            await self._initialize_tool(
                                tool=tool,
                                binding_type=adhesive,
                                conversation_id=self.active_conversation,
                                model_name=model.name
                            )
                            
                            # Execute tool through model
                            result = await model.use_tool(tool_name, adhesive, tool_input)
                            tool_duration = (datetime.now() - tool_start).total_seconds()
                            
                            # Record usage
                            self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

                            # If using GLUE adhesive, share with team members
                            if adhesive == AdhesiveType.GLUE and hasattr(model, 'team'):
                                team = model.team
                                # Share result with all team members
                                for member_name in team.members:
                                    if member_name != model.name:  # Don't send to self
                                        await model.send_message(member_name, {
                                            'type': 'tool_result',
                                            'tool': tool_name,
                                            'result': result
                                        })
                            
                            # Record success
                            self.tool_optimizer.record_usage(
                                tool_name=tool_name,
                                input_type=type(tool_input).__name__,
                                output_type=type(result).__name__,
                                success=True,
                                execution_time=tool_duration,
                                context=context
                            )
                            
                            # Store result
                            self.history.append({
                                "role": "tool",
                                "tool": tool_name,
                                "content": result,
                                "timestamp": datetime.now().isoformat(),
                                "conversation_id": self.active_conversation
                            })
                            
                            # Store in memory
                            self.memory_manager.store(
                                key=f"result_{tool_name}_{datetime.now().isoformat()}",
                                content=result,
                                memory_type="short_term",
                                context=context
                            )
                            
                            # Update input for next iteration
                            current_input = f"Tool output: {result}"
                            continue
                            
                        except Exception as e:
                            error = f"Tool execution failed: {str(e)}"
                            self.logger.error(error)
                            
                            # Record failure
                            self.tool_optimizer.record_usage(
                                tool_name=tool_name,
                                input_type=type(tool_input).__name__,
                                output_type="error",
                                success=False,
                                execution_time=(datetime.now() - tool_start).total_seconds(),
                                context=context
                            )
                            
                            # Store error
                            self.history.append({
                                "role": "error",
                                "content": error,
                                "timestamp": datetime.now().isoformat(),
                                "conversation_id": self.active_conversation
                            })
                            return error
                    else:
                        error = f"Tool not available: {tool_name}"
                        self.logger.error(error)
                        return error
                
                # Save if sticky
                if self.sticky:
                    self._save_history()
                
                return response
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.logger.error(error_msg)
            self.history.append({
                "role": "error",
                "content": error_msg,
                "timestamp": datetime.now().isoformat(),
                "conversation_id": self.active_conversation
            })
            if self.sticky:
                self._save_history()
            return f"Error: {error_msg}"

    def _get_binding_type(self, tool: Any) -> AdhesiveType:
        """
        Determine appropriate binding type for a tool
        
        Args:
            tool: Tool to analyze
        """
        # Check tool configuration
        if hasattr(tool, 'sticky') and tool.sticky:
            return AdhesiveType.GLUE
            
        if hasattr(tool, 'binding_type'):
            return tool.binding_type
            
        # Default to VELCRO for session persistence
        return AdhesiveType.VELCRO

    def _enhance_input_with_context(
        self,
        current_input: str,
        context: Dict[str, Any],
        complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    ) -> str:
        """
        Format context like a natural conversation
        
        Args:
            current_input: The current user input
            context: The conversation context
            complexity: The task complexity level
        """
        # Format recent messages like chat
        history = []
        for msg in context.get("recent_history", [])[-3:]:  # Last 3 messages
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                history.append(f"Previous request: {content}")
            elif role == 'assistant':
                history.append(f"My response: {content}")
            elif role == 'tool':
                history.append(f"Tool result: {content}")
        history_str = "\n".join(history)
        
        # Format shared info like team resources
        shared_items = []
        for key, value in context.get("shared_memory", {}).items():
            if isinstance(value, dict) and 'content' in value:
                shared_items.append(f"- {key}: {value['content']}")
            else:
                shared_items.append(f"- {key}: {value}")
        shared_str = "\n".join(shared_items)
        
        # Format interaction style based on complexity
        style_str = ""
        if complexity == ComplexityLevel.SIMPLE:
            style_str = "Interaction style:\n- Keep responses direct and straightforward"
        elif complexity == ComplexityLevel.MODERATE:
            style_str = "Interaction style:\n- Provide detailed analysis and context"
        else:  # COMPLEX
            style_str = "Interaction style:\n- Break down complex tasks into clear steps"
        
        # Combine everything naturally
        context_parts = []
        if history_str:
            context_parts.append(f"Recent conversation:\n{history_str}")
        if shared_str:
            context_parts.append(f"Shared team resources:\n{shared_str}")
        if style_str:
            context_parts.append(style_str)
        
        context_str = "\n\n".join(context_parts)
        
        return f"""{context_str}

Current request:
{current_input}"""

    def _enhance_role_with_tools(self, role: str, tools: List[str]) -> str:
        """
        Enhance role description with available tool capabilities.
        
        Adds natural language descriptions of what the model can do with each tool,
        making it easier for the model to understand its capabilities.
        
        Args:
            role: Base role description
            tools: List of available tool names
        
        Returns:
            Enhanced role description with tool capabilities
        """
        enhanced = role
        
        # Add tool capabilities
        if tools:
            tool_descriptions = {
                "web_search": "search and retrieve information from the internet",
                "file_handler": "create, read, update, and delete files",
                "code_interpreter": "write, execute, and analyze code"
            }
            
            capabilities = []
            for tool in tools:
                desc = tool_descriptions.get(tool)
                if desc:
                    capabilities.append(desc)
                else:
                    # For unknown tools, use the name as a base description
                    desc = tool.replace('_', ' ').lower()
                    capabilities.append(f"use {desc}")
            
            # Add capabilities in a natural way
            if capabilities:
                enhanced += "\n\nYour capabilities include:\n"
                enhanced += "\n".join(f"- {cap}" for cap in capabilities)
        
        # Apply any tool usage patterns
        for pattern, replacement in self.TOOL_PATTERNS.items():
            enhanced = re.sub(pattern, replacement, enhanced)
        
        return enhanced

    def _get_model_context(self, model_name: str) -> Dict[str, Any]:
        """Get context for model"""
        context = {
            "recent_history": [],
            "shared_memory": {},
            "model_state": self.model_states.get(model_name, {})
        }
        
        # Get recent history
        recent = [
            msg for msg in self.memory_manager.short_term.values()
            if isinstance(msg.content, dict) and 
            msg.content.get("role") in ["user", "assistant", "tool"]
        ][-5:]
        context["recent_history"] = [msg.content for msg in recent]
        
        # Get shared memory
        if model_name in self.memory_manager.shared:
            context["shared_memory"] = {
                key: segment.content
                for key, segment in self.memory_manager.shared[model_name].items()
            }
        
        return context

    def _synthesize_responses(self, responses: List[Dict[str, Any]]) -> str:
        """
        Synthesize multiple responses into a formatted message for team communication.
        
        This method combines multiple responses, tool outputs, and file operations
        into a clean, formatted message that can be shared with other teams.
        Particularly useful when a team needs to share results through the
        magnetic field system.
        
        Args:
            responses: List of responses and tool outputs to combine
        
        Returns:
            A formatted message suitable for team-to-team communication
        """
        if not responses:
            return "No response generated"
            
        last_response = responses[-1]
        
        # Handle file operations
        if (isinstance(last_response["content"], dict) and 
            "operation" in last_response["content"] and 
            "path" in last_response["content"]):
            operation = last_response["content"]["operation"]
            path = last_response["content"]["path"]
            filename = os.path.basename(path)
            
            operations = {
                "write": f"I've saved the content to '{filename}'",
                "append": f"I've added the content to '{filename}'",
                "read": f"Here's the content of '{filename}':\n{last_response['content']['content']}",
                "delete": f"I've deleted '{filename}'"
            }
            
            return operations.get(operation, str(last_response["content"]))
        
        return str(last_response["content"])

    def _get_history_path(self) -> str:
        """Get history file path"""
        os.makedirs(self.workspace_dir, exist_ok=True)
        return os.path.join(self.workspace_dir, "chat_history.json")
    
    def _save_history(self) -> None:
        """Save history if sticky"""
        if not self.sticky:
            return
        
        path = self._get_history_path()
        with open(path, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def _load_history(self) -> None:
        """Load history if sticky"""
        if not self.sticky:
            return
            
        path = self._get_history_path()
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.history = json.load(f)
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.history
    
    def clear_history(self) -> None:
        """Clear history"""
        self.history = []
        self.memory_manager.clear("short_term")
        if self.sticky:
            path = self._get_history_path()
            if os.path.exists(path):
                os.remove(path)
    
    def save_state(self) -> Dict[str, Any]:
        """Save manager state"""
        state = {
            "history": self.history,
            "active_conversation": self.active_conversation,
            "model_states": self.model_states,
            "tool_usage": self.tool_usage,
            "resource_pool": self.resource_pool,
            "interaction_success": self.interaction_success
        }
        if self.sticky:
            self._save_history()
        return state
    
    def load_state(self, state: Dict[str, Any]) -> None:
        """Load manager state"""
        if self.sticky:
            self._load_history()
        else:
            self.history = state.get("history", [])
        self.active_conversation = state.get("active_conversation")
        self.model_states = state.get("model_states", {})
        self.tool_usage = state.get("tool_usage", {})
        self.resource_pool = state.get("resource_pool", {})
        self.interaction_success = state.get("interaction_success", {})
