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
from ..core.app import GlueApp, AppConfig
from ..core.team import Team, TeamRole
from ..core.workspace import WorkspaceManager
from ..core.conversation import ConversationManager
from ..core.tool_binding import ToolBinding
from ..core.group_chat import GroupChatManager
from ..core.logger import setup_logging, get_logger
from ..magnetic.field import MagneticField

# Tool system imports
from ..tools.base import BaseTool, ToolConfig as BaseToolConfig
from ..tools.code_interpreter import CodeInterpreterTool
from ..tools.web_search import WebSearchTool
from ..tools.file_handler import FileHandlerTool

# Provider imports
from ..providers.base import BaseProvider
from ..providers.openrouter import OpenRouterProvider

class GlueExecutor:
    """
    Executor for GLUE Applications.
    
    Core Features:
    - Team Management
      * Creates and configures teams from workflow definitions
      * Sets up team relationships (attractions, repulsions, pulls)
      * Manages tool sharing and persistence through adhesive types
    
    - Tool Configuration
      * Handles specialized tool setups (code_interpreter, web_search, etc.)
      * Manages tool bindings and workspaces
      * Provides proper API key and environment handling
    
    - Model Integration
      * Configures models with appropriate system prompts
      * Sets up tool access with clear usage examples
      * Manages model-tool bindings through adhesive system
    
    - Workflow Execution
      * Processes user input through appropriate teams
      * Follows magnetic field rules for team communication
      * Maintains state persistence based on configuration
    
    This executor serves as the core runtime for GLUE applications,
    orchestrating the interaction between teams, tools, and models
    while respecting magnetic field rules and adhesive bindings.
    """
    
    def __init__(self, app_config: GlueAppConfig):
        # Store app config
        self.app_config = app_config
        
        # Initialize logger
        self._setup_logger()
        self.logger = get_logger("glue_executor")
        
        # Initialize workspace manager and get workspace path
        self.workspace_manager = WorkspaceManager()
        sticky = self.app_config.config.get("sticky", False)
        self.workspace_path = self.workspace_manager.get_workspace(self.app_config.name, sticky)
        self.logger.debug(f"Using workspace: {self.workspace_path}")
        
        # Convert parsed config to AppConfig
        app_config_obj = AppConfig(
            name=app_config.name,
            memory_limit=app_config.config.get("memory_limit", 1000),
            enable_persistence=sticky,
            development=app_config.config.get("development", False),
            sticky=sticky,
            config=app_config.config
        )
        
        # Create GlueApp instance with workspace path
        self.app = GlueApp(
            name=app_config.name,
            config=app_config_obj,
            workspace_dir=self.workspace_path
        )
        self.tools = {}
        self.models = {}
        self.teams = {}
        
        # Determine app complexity based on team count
        is_complex = False
        if app_config.workflow:
            team_count = len(app_config.workflow.teams)
            if team_count > 1:
                self.logger.info(f"Complex app detected with {team_count} teams")
                is_complex = True
            else:
                self.logger.info("Simple app detected with single team")
        else:
            self.logger.info("Simple app detected with no workflow")
            
        # Initialize managers
        self.conversation = ConversationManager(sticky=sticky)
        self.group_chat = GroupChatManager(app_config.name)
        self.logger.debug("Initializing conversation and group chat managers")
        self._setup_environment()
    
    def _setup_logger(self):
        """Setup logging"""
        # Create output directory if it doesn't exist
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Initialize logger with development mode and log directory
        setup_logging(
            log_file=str(output_dir / f"{self.app_config.name}.log"),
            development=self.app_config.config.get("development", False)
        )
    
    def _setup_environment(self):
        """Setup execution environment"""
        # Ensure workspace exists
        os.makedirs(self.workspace_path, exist_ok=True)
    
    async def execute(self) -> GlueApp:
        """Execute the GLUE application
        
        Returns:
            GlueApp: The configured and running application instance
        """
        # Initialize components
        await self._init_tools()
        # Initialize models first
        await self._init_models()
        # Initialize teams and link models
        await self._init_teams()
        
        # Return configured app
        return self.app
    
    def _validate_tool_config(self, name: str, config: ToolConfig) -> Dict[str, Any]:
        """Validate tool configuration and return normalized config.
        
        Args:
            name: Tool name
            config: Tool configuration
            
        Returns:
            Normalized configuration dictionary
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not config or not isinstance(config.config, dict):
            raise ValueError(f"Invalid configuration for tool {name}")
            
        tool_config = config.config
        base_config = {
            "name": name,
            "workspace_dir": str(Path(self.workspace_path)),
            "adhesive_type": tool_config.get("adhesive_type", "tape")  # Default to tape if not specified
        }
        
        if name == "code_interpreter":
            # Validate required code interpreter settings
            supported_langs = tool_config.get("supported_languages")
            if not supported_langs or not isinstance(supported_langs, (list, tuple)):
                raise ValueError(f"Tool {name} requires valid supported_languages list")
                
            return {
                **base_config,
                "description": "Execute code in various languages",
                "supported_languages": supported_langs,
                "enable_security_checks": bool(tool_config.get("enable_security_checks", True)),
                "enable_code_analysis": bool(tool_config.get("enable_code_analysis", True)),
                "enable_error_suggestions": bool(tool_config.get("enable_error_suggestions", True)),
                "max_memory_mb": int(tool_config.get("max_memory_mb", 500)),
                "max_execution_time": int(tool_config.get("max_execution_time", 30)),
                "max_file_size_kb": int(tool_config.get("max_file_size_kb", 10240)),
                "max_subprocess_count": int(tool_config.get("max_subprocess_count", 2))
            }
        elif name == "web_search":
            # Validate web search settings
            if "api_key" not in tool_config and "api_key_env" not in tool_config:
                raise ValueError(f"Tool {name} requires either api_key or api_key_env")
            return base_config
        elif name == "file_handler":
            # Validate file handler settings
            if not self.workspace_path:
                raise ValueError(f"Tool {name} requires valid workspace path")
            return {
                **base_config,
                "description": "Handle file operations"
            }
        else:
            return {
                **base_config,
                "description": f"Generic tool: {name}"
            }

    def _create_tool(self, name: str, config: ToolConfig) -> BaseTool:
        """Create a tool instance based on configuration.
        
        Args:
            name: Tool name
            config: Tool configuration
            
        Returns:
            Configured tool instance
            
        Raises:
            ValueError: If tool configuration is invalid
            RuntimeError: If tool creation fails
        """
        try:
            # Validate and normalize config
            tool_config = self._validate_tool_config(name, config)
            
            # Create appropriate tool instance
            if name == "code_interpreter":
                return CodeInterpreterTool(**tool_config)
            elif name == "web_search":
                return WebSearchTool(**tool_config)
            elif name == "file_handler":
                return FileHandlerTool(**tool_config)
            else:
                return BaseTool(**tool_config)
        except Exception as e:
            raise ValueError(f"Failed to create tool {name}: {str(e)}")

    async def _init_tools(self) -> None:
        """Initialize tools.
        
        Raises:
            RuntimeError: If tool initialization fails
        """
        try:
            self.logger.info("Initializing tools...")
            for name, config in self.app_config.tool_configs.items():
                self.logger.debug(f"Setting up tool: {name}")
                tool = self._create_tool(name, config)
                self.tools[name] = tool
                self.app._tool_registry[name] = tool
        except Exception as e:
            self.logger.error(f"Tool initialization failed: {str(e)}")
            raise RuntimeError("Failed to initialize tools") from e
    
    def _validate_model_config(self, name: str, config: ModelConfig) -> Dict[str, Any]:
        """Validate model configuration and return normalized config.
        
        Args:
            name: Model name
            config: Model configuration
            
        Returns:
            Normalized configuration dictionary
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not config or not isinstance(config.config, dict):
            raise ValueError(f"Invalid configuration for model {name}")
            
        model_config = config.config
        
        # Validate provider
        if not config.provider:
            raise ValueError(f"Model {name} requires a provider")
        if config.provider not in ["openrouter", "base"]:
            raise ValueError(f"Unsupported provider {config.provider} for model {name}")
            
        # Validate role
        if not config.role:
            raise ValueError(f"Model {name} requires a role")
            
        # Validate adhesives
        adhesives = model_config.get("adhesives", [])
        if not isinstance(adhesives, (list, tuple)):
            raise ValueError(f"Model {name} adhesives must be a list")
        valid_adhesives = {"glue", "velcro", "tape"}
        invalid_adhesives = set(adhesives) - valid_adhesives
        if invalid_adhesives:
            raise ValueError(f"Invalid adhesives for model {name}: {invalid_adhesives}")
            
        # Normalize numeric values
        try:
            temperature = float(model_config.get("temperature", 0.7))
            if not 0 <= temperature <= 1:
                raise ValueError(f"Temperature must be between 0 and 1")
                
            max_tokens = int(model_config.get("max_tokens", 1000))
            if max_tokens <= 0:
                raise ValueError(f"Max tokens must be positive")
                
            top_p = float(model_config.get("top_p", 1.0))
            if not 0 <= top_p <= 1:
                raise ValueError(f"Top p must be between 0 and 1")
                
            presence_penalty = float(model_config.get("presence_penalty", 0.0))
            frequency_penalty = float(model_config.get("frequency_penalty", 0.0))
            
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid numeric values in model {name} config: {str(e)}")
            
        # Validate sequences
        stop_sequences = model_config.get("stop_sequences", [])
        if not isinstance(stop_sequences, (list, tuple)):
            raise ValueError(f"Stop sequences must be a list for model {name}")
            
        return {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "stop_sequences": stop_sequences,
            "system_prompt": None,  # Will be set by set_role
            "config": model_config  # Keep provider-specific config
        }

    def _create_model(self, name: str, config: ModelConfig) -> BaseProvider:
        """Create a model instance based on configuration.
        
        Args:
            name: Model name
            config: Model configuration
            
        Returns:
            Configured model provider instance
            
        Raises:
            ValueError: If model configuration is invalid
            RuntimeError: If model creation fails
        """
        try:
            # Validate and normalize config
            validated_config = self._validate_model_config(name, config)
            
            # Create runtime config
            from ..core.model import ModelConfig as RuntimeConfig
            runtime_config = RuntimeConfig(**validated_config)
            
            # Create provider instance
            provider_cls = OpenRouterProvider if config.provider == "openrouter" else BaseProvider
            provider = provider_cls(
                name=name,
                team=None,  # Team will be set during team initialization
                available_adhesives=set(config.config.get("adhesives", [])),
                config=runtime_config
            )
            
            if not config.role:
                raise ValueError(f"Model {name} requires a role")
            provider.set_role(config.role)
            
            return provider
            
        except Exception as e:
            raise ValueError(f"Failed to create model {name}: {str(e)}")

    async def _init_models(self) -> None:
        """Initialize models.
        
        Raises:
            RuntimeError: If model initialization fails
        """
        try:
            self.logger.info("Initializing models...")
            for name, config in self.app_config.model_configs.items():
                self.logger.debug(f"Setting up model: {name} with provider {config.provider}")
                provider = self._create_model(name, config)
                self.models[name] = provider
                await self.app.add_model(provider)
        except Exception as e:
            self.logger.error(f"Model initialization failed: {str(e)}")
            raise RuntimeError("Failed to initialize models") from e
    
    async def _create_team(self, name: str, config: Any) -> Team:
        """Create a team instance based on configuration.
        
        Args:
            name: Team name
            config: Team configuration
            
        Returns:
            Configured team instance
            
        Raises:
            ValueError: If team configuration is invalid
        """
        try:
            # Get team models
            team_models = {}
            if config.lead:
                if config.lead not in self.models:
                    raise ValueError(f"Lead model {config.lead} not found")
                team_models[config.lead] = self.models[config.lead]
            
            for member_name in config.members:
                if member_name not in self.models:
                    raise ValueError(f"Member model {member_name} not found")
                team_models[member_name] = self.models[member_name]

            # Create team with models
            team = Team(name=name, models=team_models)
            
            # Add lead if specified
            if config.lead:
                await team.add_member(config.lead, role=TeamRole.LEAD)
            
            # Add members
            for member_name in config.members:
                await team.add_member(member_name)
            
            # Add tools to team
            for tool_name in config.tools:
                if tool_name not in self.tools:
                    raise ValueError(f"Tool {tool_name} not found")
                tool = self.tools[tool_name]
                await team.add_tool(tool)
                self.logger.debug(f"Added tool {tool_name} to team {name}")
            
            # Initialize shared results
            team.shared_results = {}
            
            # Link models to team and connect to group chat
            if config.lead:
                lead_model = self.models[config.lead]
                lead_model.team = team
                self.group_chat.add_model(lead_model)
            for member_name in config.members:
                member_model = self.models[member_name]
                member_model.team = team
                self.group_chat.add_model(member_model)
            
            return team
            
        except Exception as e:
            raise ValueError(f"Failed to create team {name}: {str(e)}")

    async def _setup_magnetic_field(self) -> None:
        """Setup magnetic field for team interactions.
        
        Raises:
            ValueError: If magnetic field configuration is invalid
        """
        try:
            self.logger.info("Setting up magnetic field...")
            field = MagneticField(name=self.app.name)
            
            # Register all teams
            for team_name in self.teams:
                await field.add_team(self.teams[team_name])
            
            # Add attractions (push flow)
            for source, target in self.app_config.workflow.attractions:
                if source not in self.teams or target not in self.teams:
                    raise ValueError(f"Invalid attraction flow: {source} -> {target}")
                await field.process_team_flow(source, target, None, "->")
            
            # Add repulsions    
            for source, target in self.app_config.workflow.repulsions:
                if source not in self.teams or target not in self.teams:
                    raise ValueError(f"Invalid repulsion flow: {source} <> {target}")
                await field.process_team_flow(source, target, None, "<>")
                
            # Enable pull capability
            for target, source in self.app_config.workflow.pulls:
                if source == "pull":
                    if target not in self.teams:
                        raise ValueError(f"Invalid pull target: {target}")
                    await field.enable_pull(target, "researchers")
            
            self.app.magnetic_field = field
            
        except Exception as e:
            raise ValueError(f"Failed to setup magnetic field: {str(e)}")

    async def _init_teams(self) -> None:
        """Initialize teams and setup magnetic field.
        
        Raises:
            RuntimeError: If team initialization fails
        """
        if not self.app_config.workflow:
            return
            
        try:
            self.logger.info("Initializing teams...")
            for name, config in self.app_config.workflow.teams.items():
                self.logger.debug(f"Setting up team: {name}")
                team = await self._create_team(name, config)
                self.teams[name] = team
                await self.app.add_team(team)
            
            await self._setup_magnetic_field()
            
        except Exception as e:
            self.logger.error(f"Team initialization failed: {str(e)}")
            raise RuntimeError("Failed to initialize teams") from e

def _print_app_summary(app: GlueApp, executor: GlueExecutor):
    """Print summary of app structure"""
    logger = get_logger("glue_app_summary")
    
    # Log app initialization with user_facing flag for minimal output
    logger.info(f"\n{app.name} is ready.", extra={"user_facing": True})
    logger.info("\nEnter prompts or 'exit' to quit.", extra={"user_facing": True})
    
    # Log detailed info for debugging
    logger.debug(f"Workspace: {executor.workspace_path}")
    
    for team_name, team in app.teams.items():
        logger.debug(f"\nTeam: {team_name}")
        logger.debug(f"  Lead: {team.lead}")
        if team.members:
            logger.debug(f"  Members: {', '.join(team.members)}")
        if team.tools:
            logger.debug(f"  Tools: {', '.join(team.tools.keys())}")
            
    if app.magnetic_field:
        logger.debug("\nMagnetic Flows:")
        for flow_state in app.magnetic_field.state.active_flows.values():
            source = flow_state.config.source
            target = flow_state.config.target
            flow_type = flow_state.config.flow_type
            
            if flow_type == "><":
                logger.debug(f"  {source} <-> {target}")
            elif flow_type == "->":
                logger.debug(f"  {source} -> {target}")
            elif flow_type == "<-":
                logger.debug(f"  {source} <- {target}")

async def execute_glue_app(app_config: GlueAppConfig) -> GlueApp:
    """Execute GLUE application
    
    Args:
        app_config: The GLUE application configuration
        
    Returns:
        GlueApp: The configured and running application instance
    """
    executor = GlueExecutor(app_config)
    app = await executor.execute()
    _print_app_summary(app, executor)
    return app
