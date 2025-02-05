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
from ..core.logger import init_logger, get_logger
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
        # Store app config first
        self.app_config = app_config
        
        # Initialize logger
        self._setup_logger()
        self.logger = get_logger()
        
        # Initialize workspace manager and get workspace path
        self.workspace_manager = WorkspaceManager()
        sticky = self.app_config.config.get("sticky", False)
        self.workspace_path = self.workspace_manager.get_workspace(self.app_config.name, sticky)
        self.logger.info(f"Using workspace: {self.workspace_path}")
        
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
        self.app_config = app_config
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
        init_logger(
            name=self.app_config.name,
            log_dir=str(output_dir),
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
    
    async def _init_tools(self):
        """Initialize tools"""
        self.logger.info("Initializing tools...")
        for name, config in self.app_config.tool_configs.items():
            self.logger.info(f"Setting up tool: {name}")
            # Create tool instance based on type
            if name == "code_interpreter":
                tool = CodeInterpreterTool(
                    name=name,
                    description="Execute code in various languages",
                    workspace_dir=str(Path(self.workspace_path)),
                    supported_languages=config.config.get("supported_languages"),
                    adhesive_type=config.config.get("adhesive_type"),
                    enable_security_checks=config.config.get("enable_security_checks", True),
                    enable_code_analysis=config.config.get("enable_code_analysis", True),
                    enable_error_suggestions=config.config.get("enable_error_suggestions", True),
                    max_memory_mb=config.config.get("max_memory_mb", 500),
                    max_execution_time=config.config.get("max_execution_time", 30),
                    max_file_size_kb=config.config.get("max_file_size_kb", 10240),
                    max_subprocess_count=config.config.get("max_subprocess_count", 2)
                )
            elif name == "web_search":
                tool = WebSearchTool()
                tool.adhesive_type = config.config.get("adhesive_type")
            elif name == "file_handler":
                tool = FileHandlerTool(
                    name=name,
                    description="Handle file operations",
                    workspace_dir=str(Path(self.workspace_path)),
                    adhesive_type=config.config.get("adhesive_type")
                )
            else:
                tool = BaseTool(
                    name=name,
                    description=f"Generic tool: {name}",
                    adhesive_type=config.config.get("adhesive_type")
                )
            
            self.tools[name] = tool
            self.app._tool_registry[name] = tool  # Store in persistent registry
    
    async def _init_models(self):
        """Initialize models"""
        self.logger.info("Initializing models...")
        for name, config in self.app_config.model_configs.items():
            self.logger.info(f"Setting up model: {name} with provider {config.provider}")
            available_adhesives = set(config.config.get("adhesives", []))
            
            # Convert parser config to runtime config
            from ..core.model import ModelConfig as RuntimeConfig
            runtime_config = RuntimeConfig(
                temperature=config.config.get("temperature", 0.7),
                max_tokens=config.config.get("max_tokens", 1000),
                top_p=config.config.get("top_p", 1.0),
                presence_penalty=config.config.get("presence_penalty", 0.0),
                frequency_penalty=config.config.get("frequency_penalty", 0.0),
                stop_sequences=config.config.get("stop_sequences", []),
                system_prompt=None,  # Will be set by set_role
                config=config.config  # Keep provider-specific config
            )

            # Create provider with role
            if config.provider == "openrouter":
                provider = OpenRouterProvider(
                    name=name,
                    team=None,  # Team will be set during team initialization
                    available_adhesives=available_adhesives,
                    config=runtime_config
                )
            else:
                provider = BaseProvider(
                    name=name,
                    team=None,  # Team will be set during team initialization
                    available_adhesives=available_adhesives,
                    config=runtime_config
                )
            
            # Set role and system prompt
            provider.set_role(config.role)
            
            self.models[name] = provider
            await self.app.add_model(provider)
    
    async def _init_teams(self):
        """Initialize teams"""
        if not self.app_config.workflow:
            return
            
        self.logger.info("Initializing teams...")
        # Create teams
        for name, config in self.app_config.workflow.teams.items():
            self.logger.info(f"Setting up team: {name}")
            # Get team models
            team_models = {}
            if config.lead:
                team_models[config.lead] = self.models[config.lead]
            for member_name in config.members:
                team_models[member_name] = self.models[member_name]

            # Create team with models
            team = Team(
                name=name,
                models=team_models
            )
            
            # Add lead if specified
            if config.lead:
                await team.add_member(config.lead, role=TeamRole.LEAD)
            
            # Add members
            for member_name in config.members:
                await team.add_member(member_name)
            
            # Add tools to team
            for tool_name in config.tools:
                if tool_name in self.tools:
                    tool = self.tools[tool_name]
                    # Add tool to team without binding - models will use their own adhesives
                    await team.add_tool(tool)
                    self.logger.debug(f"Added tool {tool_name} to team {name}")
                else:
                    self.logger.error(f"Tool {tool_name} not found")
            
            # Store team
            self.teams[name] = team
            await self.app.add_team(team)
            
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
            
        # Setup magnetic field
        if self.app_config.workflow:
            self.logger.info("Setting up magnetic field...")
            field = MagneticField(name=self.app.name)
            
            # Register all teams with the field first
            for team_name in self.teams:
                await field.add_team(self.teams[team_name])
            
            # Add attractions (push flow)
            for source, target in self.app_config.workflow.attractions:
                await field.process_team_flow(source, target, None, "->")
            
            # Add repulsions    
            for source, target in self.app_config.workflow.repulsions:
                await field.process_team_flow(source, target, None, "<>")
                
            # Enable pull capability for teams that use the pull keyword
            for target, source in self.app_config.workflow.pulls:
                if source == "pull":
                    # Enable pull capability for the target team from researchers
                    await field.enable_pull(target, "researchers")
            
            self.app.magnetic_field = field

async def execute_glue_app(app_config: GlueAppConfig) -> GlueApp:
    """Execute GLUE application
    
    Args:
        app_config: The GLUE application configuration
        
    Returns:
        GlueApp: The configured and running application instance
    """
    executor = GlueExecutor(app_config)
    return await executor.execute()
