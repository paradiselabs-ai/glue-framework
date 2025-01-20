# src/glue/dsl/executor.py

"""GLUE DSL Executor"""

import os
import asyncio
from typing import Any, Dict, Set, List, Tuple, Optional, Type
from pathlib import Path
from copy import deepcopy
from .parser import GlueApp, ModelConfig, ToolConfig
from ..core.types import AdhesiveType
from ..core.workspace import workspace_context
from ..tools.base import BaseTool as create_tool
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
        self._registry = None
        
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
    
    @property
    def registry(self) -> Optional['ResourceRegistry']:
        """Get the resource registry"""
        if not self._registry:
            from ..core.registry import ResourceRegistry
            from ..core.state import StateManager
            self._registry = ResourceRegistry(StateManager())
        return self._registry
    
    @registry.setter
    def registry(self, value: 'ResourceRegistry') -> None:
        """Set the resource registry"""
        self._registry = value
    
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
                
                # Get tool type
                tool_type = _infer_tool_type(tool_name)
                if not tool_type:
                    raise ValueError(f"Unknown tool type: {tool_name}")
                
                # Create tool based on its type
                if tool_name == "code_interpreter":
                    tool = tool_type(
                        name=tool_name,
                        description="Executes code in a sandboxed environment",
                        workspace_dir=workspace_path,
                        magnetic=tool_config.config.get("magnetic", False),
                        sticky=sticky,
                        supported_languages=tool_config.config.get("languages", None)
                    )
                else:
                    # Set workspace path for file operations
                    config = {
                        **tool_config.config,
                        "sticky": sticky,
                        "workspace_dir": workspace_path
                    }
                    
                    tool = tool_type(
                        name=tool_name,
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
                    "name": model_name,  # Use role name instead of model name
                    "temperature": config.config.get("temperature", 0.7),
                    "model": config.config.get("model", "gpt-4")
                }
                
                # Print masked settings
                masked_settings = self._mask_sensitive_data(model_settings)
                self.logger.debug(f"Creating model with settings: {masked_settings}")
                
                # Create model with just model settings
                model = OpenRouterProvider(**model_settings)
                
                # Set role
                model.role = config.role
                
                # Initialize tools dictionary
                model._tools = {}
                
                self.models[model_name] = model
                self.logger.info(f"Model {model_name} setup complete")
    
    async def _setup_workflow(self, field: MagneticField):
        """Setup workflow with teams and flows"""
        if not self.app.workflow:
            return
        
        self.logger.info("\nSetting up workflow...")
        
        # First create all team fields from explicit configs
        teams = {}
        for team_name, team_config in self.app.workflow.teams.items():
            teams[team_name] = field.create_child_field(
                name=team_name,
                auto_bind=team_config.auto_bind,
                is_pull_team=team_config.is_pull_team
            )
        
        # Then setup explicit team configs
        for team_name, team_config in self.app.workflow.teams.items():
            # Get or create team field
            team_field = teams.get(team_name) or field.create_child_field(
                name=team_name,
                pull_fallback=team_config.pull_fallback,
                auto_bind=team_config.auto_bind
            )
            teams[team_name] = team_field
            
            # Add lead if specified
            if team_config.lead and team_config.lead in self.models:
                self.logger.info(f"Adding lead: {team_config.lead}")
                lead = self.models[team_config.lead]
                await team_field.add_resource(lead, is_lead=True)
                await self.group_chat.add_model(lead)
            
            # Add members
            for member_name in team_config.members:
                if member_name in self.models:
                    self.logger.info(f"Adding member: {member_name}")
                    member = self.models[member_name]
                    await team_field.add_resource(member)
                    await self.group_chat.add_model(member)
            
            # Add tools
            for tool_name in team_config.tools:
                if tool_name in self.tools:
                    self.logger.info(f"Adding tool: {tool_name}")
                    tool = self.tools[tool_name]
                    # Apply stickiness if team is sticky
                    if team_config.sticky:
                        tool.sticky = True
                    await team_field.add_resource(tool)
        
        # Setup flows between teams
        for source, target in self.app.workflow.attractions:
            self.logger.info(f"Setting up flow: {source} -> {target}")
            
            # Get team fields
            source_field = field.get_child_field(source)
            target_field = field.get_child_field(target)
            
            if source_field and target_field:
                # Enable push from source to target
                await source_field.enable_push(target_field)
            else:
                self.logger.warning(f"Could not find teams for flow: {source} -> {target}")
        
        # Setup repulsions between teams
        for source, target in self.app.workflow.repulsions:
            self.logger.info(f"Setting up repulsion: {source} <> {target}")
            
            # Get team fields
            source_field = field.get_child_field(source)
            target_field = field.get_child_field(target)
            
            if source_field and target_field:
                # Create repulsion between teams
                await source_field.repel(target_field)
            else:
                self.logger.warning(f"Could not find teams for repulsion: {source} <> {target}")
                
        # Setup pull teams and fallbacks
        for target, source in self.app.workflow.pulls:
            self.logger.info(f"Setting up pull: {target} <- {source}")
            
            # Handle special "pull" keyword
            if source.lower() == "pull":
                # Get or create target team field
                target_field = teams.get(target)
                if not target_field:
                    target_field = field.create_child_field(
                        name=target,
                        is_pull_team=True  # Mark as pull team
                    )
                    teams[target] = target_field
                else:
                    # Update existing field to be pull team
                    target_field.is_pull_team = True
                self.logger.info(f"Marked {target} as pull team")
            else:
                # Regular pull between teams
                target_field = teams.get(target)
                source_field = teams.get(source)
                
                if target_field and source_field:
                    # Enable field-level pull
                    await target_field.enable_field_pull(source_field)

    def _get_binding_patterns(self, field: MagneticField) -> Dict[str, Any]:
        """Get binding patterns from workflow"""
        patterns = {
            # Tool bindings by adhesive type
            AdhesiveType.GLUE: [],
            AdhesiveType.VELCRO: [],
            AdhesiveType.TAPE: [],
            # Include the field for context
            'field': field
        }
        
        if self.app.workflow:
            # Only add model-tool attractions
            for source, target in self.app.workflow.attractions:
                # Check if this is a model-tool attraction
                if (source in self.models and target in self.tools) or \
                   (target in self.models and source in self.tools):
                    # Use GLUE for model-tool bindings by default
                    patterns[AdhesiveType.GLUE].append((source, target))
        
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
            
            # Create workspace with existing registry
            async with workspace_context(self.app.name, self.registry) as ws:
                # Use workspace's field
                field = ws.field
                
                # Use field's context manager to ensure it stays active
                async with field as active_field:
                    # Setup tools in field
                    await self._setup_tools(active_field, workspace_path)
                    
                    # Add tools to group chat manager
                    for tool_name, tool in self.tools.items():
                        await self.group_chat.add_tool(tool)
                    
                    # Link tools to models with proper binding types
                    for model_name, model in self.models.items():
                        if hasattr(model, "_tools"):
                            model_config = self.app.model_configs[model_name]
                            if hasattr(model_config, "tools"):
                                for tool_name, binding_type in model_config.tools.items():
                                    if tool_name in self.tools:
                                        model.add_tool(tool_name, self.tools[tool_name], binding_type)
                    
                    # Setup workflow
                    await self._setup_workflow(active_field)
                    
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
                            binding_patterns = self._get_binding_patterns(active_field)
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

def _infer_tool_type(name: str) -> Optional[Type[Any]]:
    """Infer tool type from name"""
    from ..tools.code_interpreter import CodeInterpreterTool
    from ..tools.web_search import WebSearchTool
    
    TOOL_TYPES = {
        'code_interpreter': CodeInterpreterTool,
        'web_search': WebSearchTool,
    }
    
    return TOOL_TYPES.get(name.lower())

async def execute_glue_app(app: GlueApp, registry: Optional['ResourceRegistry'] = None) -> Any:
    """Execute GLUE application
    
    Args:
        app: The GLUE application to execute
        registry: Optional ResourceRegistry to use for resource management
    """
    executor = GlueExecutor(app)
    if registry:
        executor.registry = registry
    return await executor.execute()
