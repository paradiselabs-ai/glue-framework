# src/glue/dsl/executor.py

"""GLUE DSL Executor"""

import os
import asyncio
from typing import Any, Dict, Set, List, Tuple
from pathlib import Path
from copy import deepcopy
from .parser import GlueApp, ModelConfig, ToolConfig
from ..adhesive import (
    workspace_context,
    tool as create_tool,
    AdhesiveType
)
from ..providers import (
    OpenRouterProvider
)
from ..magnetic.field import MagneticField
from ..core.conversation import ConversationManager
from ..core.group_chat_flow import GroupChatManager
from ..core.workspace import WorkspaceManager
from ..core.logger import init_logger, get_logger

class GlueExecutor:
    """Executor for GLUE Applications"""
    
    def __init__(self, app: GlueApp):
        self.app = app
        self.tools = {}
        self.models = {}
        
        # Initialize logger
        self._setup_logger()
        self.logger = get_logger()
        
        # Initialize workspace manager
        self.workspace_manager = WorkspaceManager()
        
        # Initialize managers
        self.conversation = ConversationManager(
            sticky=app.config.get("sticky", False)
        )
        self.group_chat = GroupChatManager(app.name)
        self._setup_environment()
    
    def _setup_logger(self):
        """Setup logging system"""
        # Get development mode from config
        development = self.app.config.get("development", False)
        
        # Create logs directory in workspace
        log_dir = os.path.join("workspace", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize logger
        init_logger(
            name=self.app.name,
            log_dir=log_dir,
            development=development
        )
    
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data like API keys in settings"""
        masked = deepcopy(data)
        sensitive_keys = ['api_key', 'secret', 'password', 'token']
        
        def mask_value(value: str) -> str:
            if not value:
                return value
            return value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '*' * len(value)
        
        def recursive_mask(d: Dict[str, Any]) -> None:
            for k, v in d.items():
                if isinstance(v, dict):
                    recursive_mask(v)
                elif isinstance(v, str) and any(key in k.lower() for key in sensitive_keys):
                    d[k] = mask_value(v)
        
        recursive_mask(masked)
        return masked
    
    def _setup_environment(self):
        """Setup environment from .env file"""
        # Load environment variables if not already set
        if not os.getenv("OPENROUTER_API_KEY"):
            from dotenv import load_dotenv
            load_dotenv()
    
    def _determine_tool_stickiness(self, tool_config: ToolConfig) -> bool:
        """Determine tool stickiness based on app and tool config"""
        app_sticky = self.app.config.get("sticky", False)
        
        # If app isn't sticky, tools can't be sticky
        if not app_sticky:
            return False
        
        # Check if tool explicitly sets sticky
        if "sticky" in tool_config.config:
            return tool_config.config["sticky"]
        
        # Default to app stickiness
        return app_sticky
    
    async def _setup_tools(self, field: MagneticField, workspace_path: str):
        """Setup tools"""
        self.logger.info("\nSetting up tools...")
        self.logger.info(f"Available tools: {list(self.app.tool_configs.keys())}")
        
        # Print masked tool configs
        masked_configs = {
            name: self._mask_sensitive_data(config.__dict__)
            for name, config in self.app.tool_configs.items()
        }
        self.logger.debug(f"Tool configs: {masked_configs}")
        
        # Create tools with appropriate configuration
        for tool_name, tool_config in self.app.tool_configs.items():
            self.logger.info(f"\nSetting up tool: {tool_name}")
            
            # Print masked tool config
            self.logger.debug(f"Tool config: {self._mask_sensitive_data(tool_config.__dict__)}")
            
            # Get API key from environment if specified
            api_key = None
            if tool_config.api_key and tool_config.api_key.startswith("env:"):
                env_var = tool_config.api_key.replace("env:", "")
                api_key = os.getenv(env_var)
                if not api_key:
                    raise ValueError(
                        f"No API key found in environment variable {env_var} "
                        f"for tool {tool_name}"
                    )
                self.logger.info(f"Using API key from environment: {env_var}")
            
            try:
                # Create tool with config
                self.logger.info(f"Creating tool with provider: {tool_config.provider}")
                
                # Determine tool stickiness
                sticky = self._determine_tool_stickiness(tool_config)
                
                # Set workspace path for file operations
                config = {
                    **tool_config.config,
                    "sticky": sticky,
                    "workspace_dir": workspace_path
                }
                
                tool = create_tool(
                    tool_name,
                    api_key=api_key,
                    provider=tool_config.provider,
                    **config
                )
                
                # Add tool to field
                self.logger.info("Adding tool to field")
                await field.add_resource(tool)
                
                self.tools[tool_name] = tool
                self.logger.info(f"Tool {tool_name} setup complete (sticky={sticky})")
            except Exception as e:
                self.logger.error(f"Error setting up tool {tool_name}: {str(e)}")
                raise
    
    async def _setup_models(self):
        """Setup models"""
        self.logger.info("\nSetting up models...")
        self.logger.info(f"Available models: {list(self.app.model_configs.keys())}")
        
        for model_name, config in self.app.model_configs.items():
            self.logger.info(f"\nSetting up model: {model_name}")
            
            # Print masked model config
            masked_config = self._mask_sensitive_data(config.__dict__)
            self.logger.debug(f"Model config: {masked_config}")
            
            if config.provider == "openrouter":
                # Get API key from environment if specified
                api_key = None
                if config.api_key and config.api_key.startswith("env:"):
                    env_var = config.api_key.replace("env:", "")
                    api_key = os.getenv(env_var)
                    if not api_key:
                        raise ValueError(
                            f"No API key found in environment variable {env_var} "
                            f"for model {model_name}"
                        )
                else:
                    # Try default OpenRouter API key
                    api_key = os.getenv("OPENROUTER_API_KEY")
                    if not api_key:
                        raise ValueError(
                            "No OpenRouter API key found. Please set OPENROUTER_API_KEY "
                            "in your environment or specify os.api_key in your GLUE file."
                        )
                
                # Extract model configuration
                model_settings = {
                    "api_key": api_key,
                    "system_prompt": config.role,
                    "name": model_name  # Use role name instead of model name
                }
                
                # Add optional configuration
                model_settings.update(config.config)
                
                # Print masked settings
                masked_settings = self._mask_sensitive_data(model_settings)
                self.logger.debug(f"Creating model with settings: {masked_settings}")
                
                # Create model
                model = OpenRouterProvider(**model_settings)
                
                # Set role and tools
                model.role = config.role
                model._tools = {}
                for tool_name in config.tools:
                    model.add_tool(tool_name, None)  # Tools will be linked later
                
                self.models[model_name] = model
                self.logger.info(f"Model {model_name} setup complete")
    
    async def _setup_workflow(self, field: MagneticField):
        """Setup workflow attractions and repulsions"""
        if not self.app.workflow:
            return
        
        self.logger.info("\nSetting up workflow...")
        
        # Add models to field first
        for model_name, model in self.models.items():
            self.logger.info(f"Adding model to field: {model_name}")
            await field.add_resource(model)
            # Also add to group chat manager
            await self.group_chat.add_model(model)
        
        # Setup chat relationships
        if hasattr(self.app.workflow, 'chat'):
            for model1, model2 in self.app.workflow.chat:
                self.logger.info(f"Creating chat relationship: {model1} <--> {model2}")
                # Use group chat manager for bidirectional chat
                await self.group_chat.start_chat(model1, model2)
        
        # Setup magnetic attractions between models and tools
        for source, target in self.app.workflow.attractions:
            self.logger.info(f"Creating attraction: {source} >< {target}")
            
            # Get source (could be model or tool)
            source_obj = self.models.get(source) or self.tools.get(source)
            # Get target (could be model or tool)
            target_obj = self.models.get(target) or self.tools.get(target)
            
            if source_obj and target_obj:
                # Create attraction between model and tool
                await field.attract(source_obj, target_obj)
                
                # If source is a model, give it access to the tool
                if source in self.models and target in self.tools:
                    model = self.models[source]
                    if hasattr(model, "_tools"):
                        model._tools[target] = self.tools[target]
                    # Set tool relationship in group chat manager
                    await self.group_chat.set_tool_relationship(source, target, "><")
                
                # If target is a model, give it access to the tool
                if target in self.models and source in self.tools:
                    model = self.models[target]
                    if hasattr(model, "_tools"):
                        model._tools[source] = self.tools[source]
                    # Set tool relationship in group chat manager
                    await self.group_chat.set_tool_relationship(target, source, "><")
            else:
                self.logger.warning(f"Could not find objects for attraction: {source} >< {target}")
        
        # Setup repulsions
        for source, target in self.app.workflow.repulsions:
            self.logger.info(f"Creating repulsion: {source} <> {target}")
            
            # Get source (could be model or tool)
            source_obj = self.models.get(source) or self.tools.get(source)
            # Get target (could be model or tool)
            target_obj = self.models.get(target) or self.tools.get(target)
            
            if source_obj and target_obj:
                await field.repel(source_obj, target_obj)
                
                # If source is a model, remove tool access
                if source in self.models and target in self.tools:
                    model = self.models[source]
                    if hasattr(model, "_tools") and target in model._tools:
                        del model._tools[target]
                    # Set tool relationship in group chat manager
                    await self.group_chat.set_tool_relationship(source, target, "<>")
                
                # If target is a model, remove tool access
                if target in self.models and source in self.tools:
                    model = self.models[target]
                    if hasattr(model, "_tools") and source in model._tools:
                        del model._tools[source]
                    # Set tool relationship in group chat manager
                    await self.group_chat.set_tool_relationship(target, source, "<>")
            else:
                self.logger.warning(f"Could not find objects for repulsion: {source} <> {target}")

    def _get_binding_patterns(self, field: MagneticField) -> Dict[str, Any]:
        """Get binding patterns from workflow"""
        patterns = {
            AdhesiveType.GLUE_ATTRACT: [],
            AdhesiveType.VELCRO_ATTRACT: [],
            AdhesiveType.TAPE_ATTRACT: [],
            'field': field  # Include the magnetic field
        }
        
        if self.app.workflow:
            # Only add model-tool attractions to magnet pattern
            for source, target in self.app.workflow.attractions:
                # Check if this is a model-tool attraction
                if (source in self.models and target in self.tools) or \
                   (target in self.models and source in self.tools):
                    patterns[AdhesiveType.GLUE_ATTRACT].append((source, target))
        
        return patterns
    
    async def execute(self) -> Any:
        """Execute GLUE application"""
        # Setup models first (they don't need the field)
        await self._setup_models()
        
        try:
            # Get workspace based on app stickiness
            workspace_path = self.workspace_manager.get_workspace(
                self.app.name,
                sticky=self.app.config.get("sticky", False)
            )
            
            # Create registry and magnetic field for tools
            from ..core.registry import ResourceRegistry
            from ..core.state import StateManager
            registry = ResourceRegistry(StateManager())
            async with MagneticField(self.app.name, registry) as field:
                # Setup tools in field
                await self._setup_tools(field, workspace_path)
                
                # Add tools to group chat manager
                for tool_name, tool in self.tools.items():
                    await self.group_chat.add_tool(tool)
                
                # Link tools to models
                for model_name, model in self.models.items():
                    if hasattr(model, "_tools"):
                        for tool_name in list(model._tools.keys()):
                            if tool_name in self.tools:
                                model._tools[tool_name] = self.tools[tool_name]
                
                # Setup workflow
                await self._setup_workflow(field)
                
                # Create workspace
                async with workspace_context(self.app.name) as ws:
                    # Interactive prompt loop
                    while True:
                        print("\nprompt:", flush=True)
                        user_input = await asyncio.get_event_loop().run_in_executor(None, input)
                        
                        if user_input.lower() in ['exit', 'quit']:
                            break
                        
                        # Get model's response using appropriate manager
                        print("\nthinking...", flush=True)
                        
                        # Check if we have any active chats
                        active_chats = self.group_chat.get_active_conversations()
                        if active_chats:
                            # Use group chat manager for chat interactions
                            chat_id = next(iter(active_chats))
                            response = await self.group_chat.process_message(
                                chat_id,
                                user_input
                            )
                        else:
                            # Use regular conversation manager for non-chat interactions
                            binding_patterns = self._get_binding_patterns(field)
                            response = await self.conversation.process(
                                models=self.models,
                                binding_patterns=binding_patterns,
                                user_input=user_input,
                                tools=self.tools
                            )
                        
                        print(f"\nresponse: {response}", flush=True)
        finally:
            # Save conversation state if sticky
            if self.app.config.get("sticky", False):
                self.conversation.save_state()
            
            # Cleanup any remaining sessions
            for tool in self.tools.values():
                if hasattr(tool, 'cleanup'):
                    await tool.cleanup()
            
            # Cleanup group chat
            await self.group_chat.cleanup()
            
            # Cleanup workspace if not sticky
            if not self.app.config.get("sticky", False):
                self.workspace_manager.cleanup_workspace(workspace_path)

async def execute_glue_app(app: GlueApp) -> Any:
    """Execute GLUE application"""
    executor = GlueExecutor(app)
    return await executor.execute()
