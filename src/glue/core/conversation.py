# src/glue/core/conversation.py

"""GLUE Conversation Manager"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime
from pathlib import Path
from .model import Model
from .memory import MemoryManager
from .logger import get_logger
from .context import ContextAnalyzer, ContextState, InteractionType
from .role import DynamicRole, RoleState
from ..tools.chain import ToolChainOptimizer
from ..magnetic.rules import InteractionPattern
from ..core.adhesive import AdhesiveType, AdhesiveState

class ConversationManager:
    """
    Core orchestrator for model interactions and tool management in GLUE.
    
    Features:
    - Magnetic Fields: Model interaction patterns (><, ->, <-, <>)
    - Adhesive Bindings: Tool persistence levels (glue, velcro, tape)
    - Context-aware state management
    - Resource pooling
    - Memory management
    - Tool optimization
    - Event tracking
    
    The ConversationManager acts as the central coordinator for:
    1. Model-to-model communication through magnetic fields
    2. Tool persistence and sharing through adhesive bindings
    3. Context-aware workflow optimization
    4. Resource and state management
    
    This manager can be used in various scenarios including but not limited to:
    - Conversational agents (CBMs)
    - Multi-model workflows
    - Tool-augmented processing
    - Resource-aware computations
    """
    
    # Tool usage patterns
    TOOL_PATTERNS = {
        r'<tool>(.*?)</tool>': lambda m: f"Use the {m.group(1)} tool",
        r'<input>(.*?)</input>': lambda m: f"with input: {m.group(1)}",
        r'<think>(.*?)</think>': lambda m: f"Reasoning: {m.group(1)}",
        r'<error>(.*?)</error>': lambda m: f"Error: {m.group(1)}"
    }
    
    # Magnetic field patterns
    MAGNETIC_PATTERNS = {
        InteractionPattern.ATTRACT: "bidirectional",  # ><
        InteractionPattern.PUSH: "outgoing",          # ->
        InteractionPattern.PULL: "incoming",          # <-
        InteractionPattern.REPEL: "repulsion"         # <>
    }
    
    # Adhesive binding types
    ADHESIVE_TYPES = {
        "permanent": AdhesiveType.GLUE,    # Full persistence
        "session": AdhesiveType.VELCRO,    # Partial persistence
        "temporary": AdhesiveType.TAPE     # No persistence
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
        
        # Model management (Magnetic)
        self.model_states: Dict[str, Dict[str, Any]] = {}
        self.model_roles: Dict[str, DynamicRole] = {}
        self.model_patterns: Dict[str, Set[InteractionPattern]] = {}
        
        # Tool management (Adhesive)
        self.tool_instances: Dict[str, Dict[str, Any]] = {}
        self.resource_pool: Dict[str, Dict[str, Any]] = {}
        self.tool_bindings: Dict[str, Dict[str, AdhesiveType]] = {}
        
        # Performance tracking
        self.interaction_success: Dict[str, bool] = {}
        self.tool_usage: Dict[str, int] = {}
        
        # Load history if sticky
        if self.sticky:
            self._load_history()

    def _get_tool_instance(
        self,
        tool_name: str,
        conversation_id: str,
        binding_type: AdhesiveType,
        model_name: Optional[str] = None
    ) -> Any:
        """
        Get appropriate tool instance based on binding type
        
        Args:
            tool_name: Name of the tool
            conversation_id: Current conversation ID
            binding_type: Type of adhesive binding
            model_name: Optional model using the tool
        """
        # Handle based on binding type
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
        field: Any,
        binding_type: AdhesiveType,
        conversation_id: str,
        model_name: Optional[str] = None
    ) -> None:
        """
        Initialize tool with appropriate instance and binding
        
        Args:
            tool: Tool to initialize
            field: Magnetic field
            binding_type: Type of adhesive binding
            conversation_id: Current conversation ID
            model_name: Optional model using the tool
        """
        if hasattr(tool, 'magnetic') and tool.magnetic:
            # Get instance based on binding type
            instance_data = self._get_tool_instance(
                tool_name=tool.name,
                conversation_id=conversation_id,
                binding_type=binding_type,
                model_name=model_name
            )
            
            # Initialize tool
            await tool.initialize(instance_data)
            
            # Add to field if needed (magnetic aspect)
            if not tool._workspace:
                await tool.attach_to_workspace(field)
            if not field.get_resource(tool.name):
                await field.add_resource(tool)
            
            # Store binding type (adhesive aspect)
            if model_name:
                if model_name not in self.tool_bindings:
                    self.tool_bindings[model_name] = {}
                self.tool_bindings[model_name][tool.name] = binding_type

    def _determine_flow(
        self,
        binding_patterns: Dict[str, Any],
        context: Optional[ContextState] = None
    ) -> List[str]:
        """
        Determine execution flow based on magnetic patterns
        
        Args:
            binding_patterns: Magnetic field patterns
            context: Optional conversation context
        """
        flow = []
        visited = set()
        
        def should_add_component(component: str) -> bool:
            """Check if component should be added"""
            # Check model role (magnetic)
            if component in self.model_roles:
                role = self.model_roles[component]
                role_context = role.adjust_for_context(context)
                return role_context.state != RoleState.PASSIVE
                
            # Check tool based on context
            if context:
                # In chat mode, only add explicitly required tools
                if context.interaction_type == InteractionType.CHAT:
                    return component in context.tools_required
                    
                # In research/task mode, add tools that match the context
                elif context.interaction_type in [InteractionType.RESEARCH, InteractionType.TASK]:
                    return (
                        # Add tool if it's required by context
                        component in context.tools_required or
                        # Or if it's a research tool in research mode
                        (context.interaction_type == InteractionType.RESEARCH and 
                         component == "web_search") or
                        # Or if it's a code tool in task mode
                        (context.interaction_type == InteractionType.TASK and 
                         component == "code_interpreter")
                    )
                    
            # Default to True for unknown contexts
            return True
        
        def add_magnetic_chain(chain, pattern: Optional[InteractionPattern] = None):
            """Add components based on magnetic pattern"""
            for item in chain:
                if isinstance(item, (list, tuple)):
                    if len(item) == 2:
                        comp1, comp2 = item
                    else:
                        comp1, comp2, _ = item
                        
                    # Add based on pattern/state
                    if comp1 not in visited and should_add_component(comp1):
                        flow.append(comp1)
                        visited.add(comp1)
                        if pattern:
                            self.model_patterns[comp1].add(pattern)
                            
                    if comp2 not in visited and should_add_component(comp2):
                        flow.append(comp2)
                        visited.add(comp2)
                        if pattern:
                            self.model_patterns[comp2].add(pattern)
                else:
                    if item not in visited and should_add_component(item):
                        flow.append(item)
                        visited.add(item)
                        if pattern:
                            self.model_patterns[item].add(pattern)

        # Process magnetic patterns
        field = binding_patterns.get('field')
        if field:
            # Check if field is a pull team
            is_pull_team = hasattr(field, 'is_pull_team') and field.is_pull_team
            
            # First add non-pull patterns
            # Bidirectional (><)
            add_magnetic_chain(
                binding_patterns.get('attract', []),
                InteractionPattern.ATTRACT
            )
            
            # Push (->)
            add_magnetic_chain(
                binding_patterns.get('push', []),
                InteractionPattern.PUSH
            )
            
            # Repel (<>)
            add_magnetic_chain(
                binding_patterns.get('repel', []),
                InteractionPattern.REPEL
            )
            
            # Add pull patterns last (if pull team)
            if is_pull_team:
                add_magnetic_chain(
                    binding_patterns.get('pull', []),
                    InteractionPattern.PULL
                )
                
                # If no flow determined and this is a pull team,
                # add all non-repelled components
                if not flow:
                    repelled = set()
                    for r1, r2 in binding_patterns.get('repel', []):
                        repelled.add(r1)
                        repelled.add(r2)
                    
                    # Add all components except repelled ones
                    for component in field.list_resources():
                        if (component not in repelled and 
                            component not in visited and 
                            should_add_component(component)):
                            flow.append(component)
                            visited.add(component)
                            self.model_patterns[component].add(InteractionPattern.PULL)
        
        return flow

    async def process(
        self, 
        models: Dict[str, Model], 
        binding_patterns: Dict[str, Any],
        user_input: str,
        tools: Optional[Dict[str, Any]] = None,
        context: Optional[ContextState] = None
    ) -> str:
        """Process user input through the bound models and tools"""
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

            # Update magnetic field context if present
            field = binding_patterns.get('field')
            if field:
                await field.update_context(context)
                
                # Initialize tools only for non-chat interactions or if explicitly required
                if tools and (context.interaction_type != InteractionType.CHAT or context.tools_required):
                    for tool_name, tool in tools.items():
                        # Skip tools not required in chat mode
                        if context.interaction_type == InteractionType.CHAT and tool_name not in context.tools_required:
                            continue
                            
                        # Determine binding type from tool configuration
                        binding_type = self._get_binding_type(tool)
                        
                        await self._initialize_tool(
                            tool=tool,
                            field=field,
                            binding_type=binding_type,
                            conversation_id=self.active_conversation
                        )

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

            # Initialize/update model roles and patterns
            for model_name, model in models.items():
                # Initialize role if needed
                if model_name not in self.model_roles:
                    self.model_roles[model_name] = DynamicRole(model.role)
                    if hasattr(model, "_tools"):
                        for tool_name in model._tools:
                            self.model_roles[model_name].allow_tool(tool_name)
                
                # Initialize patterns set
                if model_name not in self.model_patterns:
                    self.model_patterns[model_name] = set()

            # Determine conversation flow (magnetic)
            flow = self._determine_flow(binding_patterns, context)
            self.logger.debug(f"Flow: {flow}")
            
            # Default to first model if no flow
            if not flow and models:
                flow = [next(iter(models.keys()))]
            
            # Optimize tool chain
            optimized_tools = []
            if tools:
                tool_names = list(tools.keys())
                optimized_tools = self.tool_optimizer.optimize_chain(tool_names, context)
                self.logger.debug(f"Optimized tools: {optimized_tools}")
            
            # Process through chain
            current_input = user_input
            responses = []
            start_time = datetime.now()
            
            for component_name in flow:
                self.logger.debug(f"Processing: {component_name}")
                
                # Handle model
                if component_name in models:
                    model = models[component_name]
                    role = self.model_roles[component_name]
                    patterns = self.model_patterns[component_name]
                    
                    # Adjust role for context
                    role_context = role.adjust_for_context(context)
                    
                    # Skip if passive
                    if role_context.state == RoleState.PASSIVE:
                        continue
                    
                    # Get model's tools
                    model_tools = []
                    if hasattr(model, "_tools"):
                        for tool_name, tool in model._tools.items():
                            # Initialize tool for this model
                            if tools and tool_name in tools:
                                binding_type = self._get_binding_type(tools[tool_name])
                                
                                await self._initialize_tool(
                                    tool=tools[tool_name],
                                    field=field,
                                    binding_type=binding_type,
                                    conversation_id=self.active_conversation,
                                    model_name=model_name
                                )
                                model_tools.append(tool_name)
                    
                    # Enhance role with tools
                    if model_tools and hasattr(model, "role"):
                        model.role = self._enhance_role_with_tools(model.role, model_tools)
                    
                    # Get context and enhance input
                    model_context = self._get_model_context(component_name)
                    enhanced_input = self._enhance_input_with_context(
                        current_input,
                        model_context,
                        patterns
                    )
                    
                    try:
                        response = await model.generate(enhanced_input)
                        
                        responses.append({
                            "component": component_name,
                            "type": "model",
                            "content": response,
                            "timestamp": datetime.now().isoformat(),
                            "patterns": list(patterns)
                        })
                        
                        # Store in memory
                        self.memory_manager.store(
                            key=f"response_{component_name}_{datetime.now().isoformat()}",
                            content=response,
                            memory_type="short_term",
                            context=context
                        )
                        
                        # Update chain
                        current_input = response
                        
                        # Store in history
                        self.history.append({
                            "role": "assistant",
                            "model": component_name,
                            "content": response,
                            "timestamp": datetime.now().isoformat(),
                            "conversation_id": self.active_conversation,
                            "patterns": list(patterns)
                        })
                        
                        self.interaction_success[component_name] = True
                        
                    except Exception as e:
                        self.logger.error(f"Error from {component_name}: {str(e)}")
                        self.interaction_success[component_name] = False
                        raise
                
                # Handle tool
                elif tools and component_name in tools:
                    tool = tools[component_name]
                    
                    # Skip if not needed
                    if (context.interaction_type == InteractionType.CHAT and
                        component_name not in context.tools_required):
                        continue
                    
                    # Skip if optimized out
                    if component_name not in optimized_tools:
                        continue
                    
                    try:
                        tool_start = datetime.now()
                        result = await tool.execute(current_input)
                        tool_duration = (datetime.now() - tool_start).total_seconds()
                        
                        # Record usage
                        self.tool_usage[component_name] = self.tool_usage.get(component_name, 0) + 1
                        
                        # Record success
                        self.tool_optimizer.record_usage(
                            tool_name=component_name,
                            input_type=type(current_input).__name__,
                            output_type=type(result).__name__,
                            success=True,
                            execution_time=tool_duration,
                            context=context
                        )
                        
                        responses.append({
                            "component": component_name,
                            "type": "tool",
                            "content": result,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Store in memory
                        self.memory_manager.store(
                            key=f"result_{component_name}_{datetime.now().isoformat()}",
                            content=result,
                            memory_type="short_term",
                            context=context
                        )
                        
                        # Update chain
                        current_input = result
                        
                        # Store in history
                        self.history.append({
                            "role": "tool",
                            "tool": component_name,
                            "content": result,
                            "timestamp": datetime.now().isoformat(),
                            "conversation_id": self.active_conversation
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Tool error {component_name}: {str(e)}")
                        self.tool_optimizer.record_usage(
                            tool_name=component_name,
                            input_type=type(current_input).__name__,
                            output_type="error",
                            success=False,
                            execution_time=(datetime.now() - tool_start).total_seconds(),
                            context=context
                        )
                        raise
                        
                else:
                    self.logger.warning(f"Unknown component: {component_name}")

            # Record chain
            total_duration = (datetime.now() - start_time).total_seconds()
            self.tool_optimizer.record_chain(
                tools=optimized_tools,
                success=True,
                execution_time=total_duration,
                context=context
            )
            
            # Learn pattern
            self.memory_manager.learn_pattern(
                trigger=user_input,
                sequence=[r["component"] for r in responses],
                success=True,
                context=context
            )

            # Save if sticky
            if self.sticky:
                self._save_history()

            # Return final response
            return self._synthesize_responses(responses)

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
        patterns: Optional[Set[InteractionPattern]] = None
    ) -> str:
        """
        Enhance input with context and patterns
        
        Args:
            current_input: Current input to enhance
            context: Context information
            patterns: Optional interaction patterns
        """
        # Get history
        history_str = "\n".join(
            f"{msg['role']}: {msg['content']}" 
            for msg in context["recent_history"]
        )
        
        # Add patterns if available
        pattern_str = ""
        if patterns:
            pattern_str = "\nAllowed interaction patterns: " + ", ".join(
                self.MAGNETIC_PATTERNS[p] for p in patterns
            )
        
        return f"""Context:{pattern_str}
{history_str}

Current Input:
{current_input}"""

    def _enhance_role_with_tools(self, role: str, tools: List[str]) -> str:
        """
        Enhance role with tool capabilities
        
        Args:
            role: Current role description
            tools: Available tools
        """
        import re
        
        enhanced = role
        
        # Add tool capabilities
        if tools:
            tool_descriptions = {
                "web_search": "search and retrieve information",
                "file_handler": "create and manage documents",
                "code_interpreter": "execute and analyze code"
            }
            
            capabilities = [
                tool_descriptions.get(tool, tool)
                for tool in tools
            ]
            
            enhanced += f"\n\nAs part of this role, you can {', '.join(capabilities)}."
        
        # Apply patterns
        for pattern, replacement in self.TOOL_PATTERNS.items():
            enhanced = re.sub(pattern, replacement, enhanced)
        
        return enhanced

    def _get_model_context(self, model_name: str) -> Dict[str, Any]:
        """
        Get context for model
        
        Args:
            model_name: Name of the model
        """
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
        Combine responses into final output
        
        Args:
            responses: List of responses to combine
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
            "interaction_success": self.interaction_success,
            "tool_usage": self.tool_usage,
            "resource_pool": self.resource_pool
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
        self.interaction_success = state.get("interaction_success", {})
        self.tool_usage = state.get("tool_usage", {})
        self.resource_pool = state.get("resource_pool", {})
