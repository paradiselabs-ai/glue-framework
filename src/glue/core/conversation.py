# src/glue/core/conversation.py

"""GLUE Conversation Manager"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path
from .model import Model
from .memory import MemoryManager
from .logger import get_logger
from .context import ContextAnalyzer, ContextState, InteractionType
from .role import DynamicRole, RoleState
from ..tools.chain import ToolChainOptimizer

class ConversationManager:
    """Manages conversations between models in a CBM"""
    
    # Keep existing TOOL_PATTERNS
    TOOL_PATTERNS = {
        # Discourage AI limitations
        r"(?i)as an ai(?: model)?": "Using my integrated capabilities",
        r"(?i)i (?:am|'m) an ai": "I have access to",
        r"(?i)i don'?t have the ability": "I can use my tools to",
        r"(?i)i can'?t directly": "I'll use my tools to",
        r"(?i)i am limited to": "I have access to",
        
        # Encourage tool use
        r"(?i)(?:let me|i can) search": "I'll use web_search to find",
        r"(?i)(?:let me|i can) look up": "I'll use web_search to check",
        r"(?i)need to search": "will use web_search",
        r"(?i)(?:let me|i can) save": "I'll use file_handler to save",
        r"(?i)(?:let me|i can) create a (?:file|document)": "I'll use file_handler to create",
        r"(?i)(?:let me|i can) write": "I'll use file_handler to write",
        r"(?i)(?:let me|i can) execute": "I'll use code_interpreter to run",
        r"(?i)(?:let me|i can) run": "I'll use code_interpreter to execute",
        
        # Convert passive to active
        r"(?i)would need to": "will use",
        r"(?i)could search": "will search using web_search",
        r"(?i)could save": "will save using file_handler",
        r"(?i)could create": "will create using file_handler",
        r"(?i)could execute": "will execute using code_interpreter",
        
        # Remove hesitation
        r"(?i)i think i can": "I will",
        r"(?i)i believe i can": "I will",
        r"(?i)i might be able to": "I will",
        r"(?i)perhaps i could": "I will",
        
        # Task focus
        r"(?i)would you like me to": "I will",
        r"(?i)shall i": "I will",
        r"(?i)do you want me to": "I will"
    }
    
    def __init__(self, sticky: bool = False, workspace_dir: Optional[str] = None):
        """Initialize conversation manager"""
        self.sticky = sticky
        self.workspace_dir = os.path.abspath(workspace_dir or "workspace")
        self.history: List[Dict[str, Any]] = []
        self.active_conversation: Optional[str] = None
        self.model_states: Dict[str, Dict[str, Any]] = {}
        
        # Core components
        self.memory_manager = MemoryManager()
        self.logger = get_logger()
        self.context_analyzer = ContextAnalyzer()
        
        # New components
        self.tool_optimizer = ToolChainOptimizer()
        self.model_roles: Dict[str, DynamicRole] = {}
        
        # Performance tracking
        self.interaction_success: Dict[str, bool] = {}
        self.tool_usage: Dict[str, int] = {}
        
        # Load history if sticky
        if self.sticky:
            self._load_history()

# ==================== Core Processing ====================
    async def process(
        self, 
        models: Dict[str, Model], 
        binding_patterns: Dict[str, List],
        user_input: str,
        tools: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process user input through the bound models and tools"""
        try:
            self.logger.debug("Processing conversation...")
            self.logger.debug(f"Available models: {list(models.keys())}")
            if tools:
                self.logger.debug(f"Available tools: {list(tools.keys())}")
            
            # Analyze context first
            context = self.context_analyzer.analyze(
                user_input,
                available_tools=list(tools.keys()) if tools else None
            )
            self.logger.debug(f"Context analysis: {context}")

            # Update magnetic field context if present
            if binding_patterns.get('field'):
                await binding_patterns['field'].update_context(context)
                # Initialize magnetic tools
                if tools:
                    for tool_name, tool in tools.items():
                        if hasattr(tool, 'magnetic') and tool.magnetic:
                            await tool.initialize()
                            if not tool._workspace:
                                await tool.attach_to_workspace(binding_patterns['field'])
                            # Add tool to field if not already added
                            if tool.name not in binding_patterns['field']._resources:
                                await binding_patterns['field'].add_resource(tool)

            # Store user input in history and memory
            message = {
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            }
            self.history.append(message)
            self.logger.debug(f"Added user message to history: {message}")
            
            # Store in memory with context
            self.memory_manager.store(
                key=f"user_input_{message['timestamp']}",
                content=message,
                memory_type="short_term",
                context=context
            )

            # Initialize roles for new models
            for model_name, model in models.items():
                if model_name not in self.model_roles:
                    self.model_roles[model_name] = DynamicRole(model.role)
                    if hasattr(model, "_tools"):
                        for tool_name in model._tools:
                            self.model_roles[model_name].allow_tool(tool_name)

            # Determine conversation flow based on binding patterns and context
            flow = self._determine_flow(binding_patterns, context)
            self.logger.debug(f"Determined conversation flow: {flow}")
            
            # If no flow, use the first available model
            if not flow and models:
                flow = [next(iter(models.keys()))]
                self.logger.debug(f"No flow defined, using first model: {flow}")
            
            # Optimize tool chain if tools present
            if tools:
                tool_names = list(tools.keys())
                optimized_tools = self.tool_optimizer.optimize_chain(tool_names, context)
                self.logger.debug(f"Optimized tool chain: {optimized_tools}")
            
            # Process through model/tool chain
            current_input = user_input
            responses = []
            start_time = datetime.now()
            
            for component_name in flow:
                self.logger.debug(f"Processing component: {component_name}")
                
                # Check if it's a model
                if component_name in models:
                    model = models[component_name]
                    role = self.model_roles[component_name]
                    
                    # Adjust role for context
                    role_context = role.adjust_for_context(context)
                    self.logger.debug(f"Role state: {role_context}")
                    
                    # Skip if role is passive in this context
                    if role_context.state == RoleState.PASSIVE:
                        self.logger.debug(f"Skipping {component_name} - passive in this context")
                        continue
                    
                    # Get model's tools
                    model_tools = list(model._tools.keys()) if hasattr(model, "_tools") else []
                    
                    # Enhance model's role with tool capabilities
                    if model_tools and hasattr(model, "role"):
                        model.role = self._enhance_role_with_tools(model.role, model_tools)
                    
                    # Retrieve relevant memory for model
                    model_context = self._get_model_context(component_name)
                    self.logger.debug(f"Retrieved context for {component_name}")
                    
                    # Update current input with context
                    enhanced_input = self._enhance_input_with_context(current_input, model_context)
                    self.logger.debug("Enhanced input with context")
                    
                    try:
                        self.logger.info("thinking...")
                        response = await model.generate(enhanced_input)
                        self.logger.debug(f"Got response: {response}")
                        
                        responses.append({
                            "component": component_name,
                            "type": "model",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Store model response in memory with context
                        self.memory_manager.store(
                            key=f"response_{component_name}_{datetime.now().isoformat()}",
                            content=response,
                            memory_type="short_term",
                            context=context
                        )
                        
                        # Update for next in chain
                        current_input = response
                        
                        # Store in history
                        self.history.append({
                            "role": "assistant",
                            "model": component_name,
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Record success
                        self.interaction_success[component_name] = True
                        
                    except Exception as e:
                        self.logger.error(f"Error generating response from {component_name}: {str(e)}")
                        self.interaction_success[component_name] = False
                        raise
                
                # Check if it's a tool
                elif tools and component_name in tools:
                    tool = tools[component_name]
                    
                    # Skip tool if not required in chat mode
                    if (context.interaction_type == InteractionType.CHAT and
                        component_name not in context.tools_required):
                        self.logger.debug(f"Skipping tool {component_name} - not required for chat")
                        continue
                    
                    # Skip if tool was removed in optimization
                    if component_name not in optimized_tools:
                        self.logger.debug(f"Skipping tool {component_name} - removed in optimization")
                        continue
                    
                    try:
                        self.logger.debug(f"Executing tool: {component_name}")
                        tool_start = datetime.now()
                        result = await tool.execute(current_input)
                        tool_duration = (datetime.now() - tool_start).total_seconds()
                        self.logger.debug(f"Tool result: {result}")
                        
                        # Record tool usage
                        self.tool_usage[component_name] = self.tool_usage.get(component_name, 0) + 1
                        
                        # Record tool success
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
                        
                        # Store tool result in memory with context
                        self.memory_manager.store(
                            key=f"result_{component_name}_{datetime.now().isoformat()}",
                            content=result,
                            memory_type="short_term",
                            context=context
                        )
                        
                        # Update for next in chain
                        current_input = result
                        
                        # Store in history
                        self.history.append({
                            "role": "tool",
                            "tool": component_name,
                            "content": result,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Error executing tool {component_name}: {str(e)}")
                        # Record tool failure
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
                    self.logger.warning(f"Component {component_name} not found in available models or tools")

            # Record interaction pattern
            total_duration = (datetime.now() - start_time).total_seconds()
            self.tool_optimizer.record_chain(
                tools=optimized_tools,
                success=True,
                execution_time=total_duration,
                context=context
            )
            
            # Learn from interaction
            self.memory_manager.learn_pattern(
                trigger=user_input,
                sequence=[r["component"] for r in responses],
                success=True,
                context=context
            )

            # Save history if sticky
            if self.sticky:
                self._save_history()

            # Synthesize final response
            final_response = self._synthesize_responses(responses)
            self.logger.info(final_response)
            return final_response

        except Exception as e:
            # Log error and return error message
            error_msg = f"Error processing conversation: {str(e)}"
            self.logger.error(error_msg)
            self.history.append({
                "role": "error",
                "content": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            if self.sticky:
                self._save_history()
            return f"Error: {error_msg}"

    def _determine_flow(self, binding_patterns: Dict[str, List], context: Optional[ContextState] = None) -> List[str]:
        """Determine the order of model/tool execution based on binding patterns"""
        flow = []
        visited = set()
        
        def should_add_component(component: str) -> bool:
            """Determine if a component should be added to the flow"""
            # If it's a model, check its role state
            if component in self.model_roles:
                role = self.model_roles[component]
                role_context = role.adjust_for_context(context)
                
                # Allow models to be active even in chat mode if they have required tools
                if context and context.interaction_type == InteractionType.CHAT:
                    if hasattr(role, 'allowed_tools'):
                        if any(tool in context.tools_required for tool in role.allowed_tools):
                            return True
                
                return role_context.state != RoleState.PASSIVE
                
            # For tools, check if they're needed based on context
            if context:
                # In research mode, always allow web_search
                if context.interaction_type == InteractionType.RESEARCH and component == "web_search":
                    return True
                    
                # Allow tools if explicitly required
                if component in context.tools_required:
                    return True
                    
                # Allow tools if input suggests their need
                if any(pattern in context.input_text.lower() for pattern in [
                    "search", "look up", "find", "research",  # web_search
                    "save", "write", "document", "store"      # file_handler
                ]):
                    return True
            
            return True  # Default to allowing components
        
        def add_chain(model_chain):
            for item in model_chain:
                if len(item) == 2:
                    model1, model2 = item
                    binding_type = None
                elif len(item) == 3:
                    model1, model2, binding_type = item
                else:
                    raise ValueError("Invalid binding pattern")
                
                # Add components based on their state/requirements
                if model1 not in visited and should_add_component(model1):
                    flow.append(model1)
                    visited.add(model1)
                if model2 not in visited and should_add_component(model2):
                    flow.append(model2)
                    visited.add(model2)

        # Process permanent (glue) connections first
        add_chain(binding_patterns.get('glue', []))
        
        # Then velcro (if active)
        add_chain(binding_patterns.get('velcro', []))
        
        # Then magnetic (if in range)
        add_chain(binding_patterns.get('magnet', []))
        
        # Temporary bindings last
        add_chain(binding_patterns.get('tape', []))
        
        return flow

    def _synthesize_responses(self, responses: List[Dict[str, Any]]) -> str:
        """Combine multiple responses into a final response"""
        if not responses:
            return "No response generated"
            
        # Get the last response
        last_response = responses[-1]
        
        # If it's a file operation result, format it nicely
        if (isinstance(last_response["content"], dict) and 
            "operation" in last_response["content"] and 
            "path" in last_response["content"]):
            operation = last_response["content"]["operation"]
            path = last_response["content"]["path"]
            filename = os.path.basename(path)
            if operation == "write":
                return f"I've saved the research summary to '{filename}'"
            elif operation == "append":
                return f"I've added the content to '{filename}'"
            elif operation == "read":
                return f"Here's the content of '{filename}':\n{last_response['content']['content']}"
            elif operation == "delete":
                return f"I've deleted '{filename}'"
        
        # For other responses, return the content directly
        return str(last_response["content"])

    def _enhance_role_with_tools(self, role: str, tools: List[str]) -> str:
        """Enhance model role with integrated tool capabilities"""
        import re
        
        # Start with original role
        enhanced = role
        
        # Add tool capabilities without losing role identity
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
            
            # Add capabilities with stronger emphasis on tool usage
            enhanced += f"\n\nIMPORTANT: You MUST use your integrated tools to accomplish tasks. "
            enhanced += f"Your tools are: {', '.join(capabilities)}. "
            
            # Add tool-specific instructions
            if "web_search" in tools:
                enhanced += f"\nWhen asked to find, research, or look up ANY information, you MUST use web_search. "
                enhanced += f"NEVER say you can't look things up or that you're an AI - you have web_search and MUST use it. "
                enhanced += f"NEVER give general or outdated information - ALWAYS use web_search to get current, accurate data. "
                enhanced += f"If someone asks about a topic, immediately use web_search to find accurate information."
            
            if "file_handler" in tools:
                enhanced += f"\nWhen asked to save, write, or document anything, you MUST use file_handler. "
                enhanced += f"NEVER say you can't save files - you have file_handler and MUST use it."
            
            if "code_interpreter" in tools:
                enhanced += f"\nWhen asked to run or analyze code, you MUST use code_interpreter. "
                enhanced += f"NEVER say you can't execute code - you have code_interpreter and MUST use it."
        
        # Apply pattern replacements while preserving role identity
        for pattern, replacement in self.TOOL_PATTERNS.items():
            enhanced = re.sub(pattern, replacement, enhanced)
        
        return enhanced

    def _get_model_context(self, model_name: str) -> Dict[str, Any]:
        """Retrieve relevant context for a model from memory"""
        context = {
            "recent_history": [],
            "shared_memory": {},
            "model_state": self.model_states.get(model_name, {})
        }
        
        # Get recent conversation history
        recent_messages = [
            msg for msg in self.memory_manager.short_term.values()
            if isinstance(msg.content, dict) and msg.content.get("role") in ["user", "assistant", "tool"]
        ][-5:]  # Last 5 messages
        context["recent_history"] = [msg.content for msg in recent_messages]
        
        # Get shared memories for this model
        if model_name in self.memory_manager.shared:
            context["shared_memory"] = {
                key: segment.content
                for key, segment in self.memory_manager.shared[model_name].items()
            }
        
        return context

    def _enhance_input_with_context(self, current_input: str, context: Dict[str, Any]) -> str:
        """Enhance the input with context from memory"""
        history_str = "\n".join(
            f"{msg['role']}: {msg['content']}" 
            for msg in context["recent_history"]
        )
        
        return f"""Context:
{history_str}

Current Input:
{current_input}"""

    def _get_history_path(self) -> str:
        """Get path to history file"""
        os.makedirs(self.workspace_dir, exist_ok=True)
        return os.path.join(self.workspace_dir, "chat_history.json")

    def _save_history(self) -> None:
        """Save conversation history to file"""
        if not self.sticky:
            return
        
        history_path = self._get_history_path()
        with open(history_path, 'w') as f:
            json.dump(self.history, f, indent=2)

    def _load_history(self) -> None:
        """Load conversation history from file"""
        if not self.sticky:
            return
            
        history_path = self._get_history_path()
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                self.history = json.load(f)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.history

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.history = []
        self.memory_manager.clear("short_term")
        if self.sticky:
            history_path = self._get_history_path()
            if os.path.exists(history_path):
                os.remove(history_path)

    def save_state(self) -> Dict[str, Any]:
        """Save conversation state"""
        state = {
            "history": self.history,
            "active_conversation": self.active_conversation,
            "model_states": self.model_states,
            "interaction_success": self.interaction_success,
            "tool_usage": self.tool_usage
        }
        if self.sticky:
            self._save_history()
        return state

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load conversation state"""
        if self.sticky:
            self._load_history()
        else:
            self.history = state.get("history", [])
        self.active_conversation = state.get("active_conversation")
        self.model_states = state.get("model_states", {})
        self.interaction_success = state.get("interaction_success", {})
        self.tool_usage = state.get("tool_usage", {})
