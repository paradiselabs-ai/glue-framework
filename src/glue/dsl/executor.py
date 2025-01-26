"""GLUE DSL Executor"""

import os
import asyncio
from typing import Any, Dict, Set, List, Tuple, Optional, Type
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict

# Core imports
from .parser import GlueAppConfig, ModelConfig, ToolConfig
from ..core.types import AdhesiveType
from ..core.app import GlueApp
from ..core.team import Team
from ..core.workspace import WorkspaceManager
from ..core.conversation import ConversationManager
from ..core.tool_binding import ToolBinding
from ..core.simple_group_chat import SimpleGroupChatManager as GroupChatManager
from ..core.logger import init_logger, get_logger

# Tool system imports
from ..tools.base import BaseTool, ToolConfig as BaseToolConfig
from ..tools.code_interpreter import CodeInterpreterTool, CodeInterpreterConfig
from ..tools.web_search import WebSearchTool
from ..tools.file_handler import FileHandlerTool

# Provider imports
from ..providers.base import BaseProvider
from ..providers.openrouter import OpenRouterProvider

class GlueExecutor:
    """Executor for GLUE Applications"""
    
    def __init__(self, app: GlueApp):
        self.app = app
        self.tools = {}
        self.models = {}
        self.teams = {}  # Initialize teams dict
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
    
    def _create_tool_config(self, tool_name: str, tool_config: ToolConfig) -> Dict[str, Any]:
        """Create tool configuration dictionary"""
        # Start with base configuration
        config = {
            "name": tool_name,
            **tool_config.config
        }
        
        # Add API key if specified
        if tool_config.api_key:
            if tool_config.api_key.startswith("env:"):
                env_var = tool_config.api_key.replace("env:", "")
                api_key = os.getenv(env_var)
                if not api_key:
                    raise ValueError(
                        f"No API key found in environment variable {env_var} "
                        f"for tool {tool_name}"
                    )
                config["api_key"] = api_key
            else:
                config["api_key"] = tool_config.api_key
        
        # Add provider if specified
        if tool_config.provider:
            config["provider"] = tool_config.provider
            
        return config
    
    async def _setup_tools(self, workspace_path: str):
        """Setup tools"""
        self.logger.info("\nSetting up tools...")
        self.logger.info(f"Available tools: {list(self.app.tool_configs.keys())}")
        
        # Print masked tool configs
        masked_configs = {
            name: self._mask_sensitive_data(asdict(config))
            for name, config in self.app.tool_configs.items()
        }
        self.logger.debug(f"Tool configs: {masked_configs}")
        
        # Create base tools
        for tool_name, tool_config in self.app.tool_configs.items():
            self.logger.info(f"\nSetting up tool: {tool_name}")
            
            try:
                # Get tool type and create configuration
                tool_type = _infer_tool_type(tool_name)
                if not tool_type:
                    raise ValueError(f"Unknown tool type: {tool_name}")
                
                # Create base configuration
                base_config = self._create_tool_config(tool_name, tool_config)
                base_config["workspace_dir"] = workspace_path
                
                # Handle special tool configurations
                if tool_type == CodeInterpreterTool:
                    # Create CodeInterpreterConfig
                    # Remove workspace_dir from base_config since we pass it explicitly
                    base_config_copy = base_config.copy()
                    base_config_copy.pop("workspace_dir", None)
                    tool_config = CodeInterpreterConfig(
                        workspace_dir=workspace_path,
                        supported_languages=base_config.get("languages"),
                        **{k: v for k, v in base_config_copy.items() 
                           if k in CodeInterpreterConfig.__annotations__}
                    )
                    base_tool = tool_type(config=tool_config)
                elif tool_name == 'web_search':
                    provider = tool_config.provider.upper()
                    api_key = os.getenv(f'{provider}_API_KEY')
                    if not api_key:
                        raise ValueError(f"No {provider}_API_KEY found in environment")
                    base_tool = tool_type(api_key=api_key, **base_config)
                else:
                    base_tool = tool_type(**base_config)
                
                self.tools[tool_name] = base_tool
                self.logger.info(f"Base tool {tool_name} setup complete")
                
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
                
                # Create model with settings
                model = OpenRouterProvider(**model_settings)
                
                # Set role
                model.role = config.role
                
                # Initialize tools dictionary
                model._tools = {}
                
                self.models[model_name] = model
                self.logger.info(f"Model {model_name} setup complete")
    
    async def _setup_workflow(self):
        """Setup workflow with teams and flows"""
        if not self.app.workflow:
            return
        
        self.logger.info("\nSetting up workflow...")
        
        # Create teams
        self.teams = {}
        for team_name, team_config in self.app.workflow.teams.items():
            self.logger.info(f"\nSetting up team: {team_name}")
            
            # Create team
            team = Team(
                name=team_name,
                members=set(),
                tools=set(),
                shared_results={},
                session_results={}
            )
            self.teams[team_name] = team
            
            # Add lead if specified
            if team_config.lead and team_config.lead in self.models:
                self.logger.info(f"Adding lead: {team_config.lead}")
                lead = self.models[team_config.lead]
                lead.team = team_name
                await team.add_member(team_config.lead)
            
            # Add members
            for member_name in team_config.members:
                if member_name in self.models:
                    self.logger.info(f"Adding member: {member_name}")
                    member = self.models[member_name]
                    member.team = team_name
                    await team.add_member(member_name)
            
            # Add tools - each model gets its own instance
            for tool_name in team_config.tools:
                if tool_name in self.tools:
                    self.logger.info(f"Adding tool: {tool_name}")
                    await team.add_tool(tool_name)
                    
                    # Create tool instance for each team member
                    base_tool = self.tools[tool_name]
                    tool_config = self.app.tool_configs[tool_name]
                    base_config = self._create_tool_config(tool_name, tool_config)
                    
                    for member_name in team.members:
                        member = self.models[member_name]
                        # Create a new instance with the same config
                        if tool_name == 'web_search':
                            # Pass api_key when creating web search instance
                            provider = tool_config.provider.upper()
                            api_key = os.getenv(f'{provider}_API_KEY')
                            if not api_key:
                                raise ValueError(f"No {provider}_API_KEY found in environment")
                            member._tools[tool_name] = WebSearchTool(api_key=api_key, **base_config)
                        elif tool_name == 'code_interpreter':
                            # Create new CodeInterpreterConfig for this instance
                            instance_config = CodeInterpreterConfig(
                                workspace_dir=self.workspace_manager.get_workspace(
                                    f"{self.app.name}-{member_name}",
                                    sticky=self.app.config.get("sticky", False)
                                ),
                                supported_languages=base_config.get("languages"),
                                **{k: v for k, v in base_config.items() 
                                   if k in CodeInterpreterConfig.__annotations__}
                            )
                            member._tools[tool_name] = CodeInterpreterTool(config=instance_config)
                        else:
                            member._tools[tool_name] = type(base_tool)(**base_config)
        
        # Setup flows between teams
        for source, target in self.app.workflow.attractions:
            self.logger.info(f"Setting up flow: {source} -> {target}")
            
            if source in self.teams and target in self.teams:
                source_team = self.teams[source]
                target_team = self.teams[target]
                # Enable bidirectional flow between teams
                source_team.set_relationship(target, None)  # None = adhesive-agnostic
                target_team.set_relationship(source, None)  # Let teams handle adhesives internally
            else:
                self.logger.warning(f"Could not find teams for flow: {source} -> {target}")
        
        # Setup repulsions between teams
        for source, target in self.app.workflow.repulsions:
            self.logger.info(f"Setting up repulsion: {source} <> {target}")
            
            if source in self.teams and target in self.teams:
                source_team = self.teams[source]
                target_team = self.teams[target]
                # Block all interaction between teams
                source_team.repel(target, bidirectional=True)
            else:
                self.logger.warning(f"Could not find teams for repulsion: {source} <> {target}")
                
        # Setup pull teams
        for target, source in self.app.workflow.pulls:
            self.logger.info(f"Setting up pull: {target} <- {source}")
            
            if target in self.teams:
                target_team = self.teams[target]
                
                # Handle special "pull" keyword
                if source.lower() == "pull":
                    # Can pull from any non-repelled team
                    for other_name, other_team in self.teams.items():
                        if other_name != target and other_name not in target_team._repelled_by:
                            # Enable pulling from non-repelled team
                            target_team.set_relationship(other_name, None)  # Adhesive-agnostic
                elif source in self.teams:
                    # Regular pull from specific team
                    # Enable specific pull relationship
                    target_team.set_relationship(source, None)  # Adhesive-agnostic

    
    async def execute(self) -> Any:
        """Execute GLUE application"""
        try:
            # Get workspace path
            workspace_path = self.workspace_manager.get_workspace(
                self.app.name,
                sticky=self.app.config.get("sticky", False)
            )
            
            # Setup components
            await self._setup_models()
            await self._setup_tools(workspace_path)
            await self._setup_workflow()
            
            # Interactive prompt loop
            while True:
                print("\nprompt:", flush=True)
                # Read input with proper buffering
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(
                    None,
                    lambda: input().strip()  # Strip whitespace
                )
                
                if user_input.lower() in ['exit', 'quit']:
                    break
                
                # Process input
                print("\nthinking...", flush=True)
                
                # Get first defined team and its lead model
                first_team = next(iter(self.teams.values()))
                if first_team and first_team.members:
                    lead_name = next(iter(first_team.members))
                    lead_model = self.models[lead_name]
                    response = await lead_model.generate(user_input)
                else:
                    # Fallback to first available model
                    model = next(iter(self.models.values()))
                    response = await model.generate(user_input)
                
                print(f"\nresponse: {response}", flush=True)
                
        finally:
            # Save state if sticky
            if self.app.config.get("sticky", False):
                for team in self.teams.values():
                    state = team.save_state()
                    # Save team state (implementation needed)
            
            # Cleanup
            for model in self.models.values():
                if hasattr(model, 'cleanup'):
                    await model.cleanup()
            
            # Cleanup workspace if not sticky
            if not self.app.config.get("sticky", False):
                self.workspace_manager.cleanup_workspace(workspace_path)

def _infer_tool_type(name: str) -> Optional[Type[BaseTool]]:
    """Infer tool type from name"""
    TOOL_TYPES = {
        'web_search': WebSearchTool,
        'file_handler': FileHandlerTool,
        'code_interpreter': CodeInterpreterTool,
    }
    
    tool_type = TOOL_TYPES.get(name.lower())
    if not tool_type:
        raise ValueError(
            f"Unknown tool type: {name}. "
            f"Available types: {list(TOOL_TYPES.keys())}"
        )
    return tool_type

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
