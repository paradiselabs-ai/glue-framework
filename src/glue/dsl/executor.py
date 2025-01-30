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
        # Create GlueApp instance from config
        self.app = GlueApp(
            name=app_config.name,
            config=AppConfig(
                name=app_config.name,
                memory_limit=1000,
                enable_persistence=app_config.config.get("sticky", False)
            )
        )
        self.app_config = app_config
        self.tools = {}
        self.models = {}
        self.teams = {}
        
        # Initialize logger
        self._setup_logger()
        self.logger = get_logger()
        
        # Initialize workspace manager
        self.workspace_manager = WorkspaceManager()
        
        # Initialize managers
        sticky = app_config.config.get("sticky", False)
        
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
        init_logger()
    
    def _setup_environment(self):
        """Setup execution environment"""
        # Create workspace if needed
        os.makedirs("workspace", exist_ok=True)
    
    async def execute(self) -> GlueApp:
        """Execute the GLUE application
        
        Returns:
            GlueApp: The configured and running application instance
        """
        # Initialize components
        await self._init_tools()
        # First pass: Initialize models without teams
        await self._init_models(with_teams=False)
        # Initialize teams with models
        await self._init_teams()
        # Second pass: Update models with their teams
        await self._init_models(with_teams=True)
        
        # Return configured app
        return self.app
    
    async def _init_tools(self):
        """Initialize tools"""
        for name, config in self.app_config.tool_configs.items():
            # Create tool instance based on type
            if name == "code_interpreter":
                tool = CodeInterpreterTool(
                    name=name,
                    description="Execute code in various languages",
                    config=config
                )
            elif name == "web_search":
                tool = WebSearchTool(
                    name=name,
                    description="Search the web for information",
                    config=config
                )
            elif name == "file_handler":
                tool = FileHandlerTool(
                    name=name,
                    description="Handle file operations",
                    config=config
                )
            else:
                tool = BaseTool(
                    name=name,
                    description=f"Generic tool: {name}",
                    config=config
                )
            
            self.tools[name] = tool
            self.app.tools[name] = tool
    
    async def _init_models(self, with_teams: bool = True):
        """Initialize models"""
        for name, config in self.app_config.model_configs.items():
            # Only get team object if with_teams is True
            team = None
            if with_teams and self.app_config.workflow:
                for team_name, team_config in self.app_config.workflow.teams.items():
                    if name in [team_config.lead] + team_config.members:
                        team = self.teams[team_name]  # Use team object instead of name
                        break
            
            # Only create new provider if it doesn't exist or we're adding teams
            if name not in self.models or with_teams:
                available_adhesives = set(config.config.get("adhesives", []))
                
                if config.provider == "openrouter":
                    provider = OpenRouterProvider(
                        name=name,
                        team=team,
                        available_adhesives=available_adhesives,
                        config=config
                    )
                else:
                    provider = BaseProvider(
                        name=name,
                        team=team,
                        available_adhesives=available_adhesives,
                        config=config
                    )
                
                self.models[name] = provider
                self.app.register_model(name, provider)
    
    async def _init_teams(self):
        """Initialize teams"""
        if not self.app_config.workflow:
            return
            
        # Create teams
        for name, config in self.app_config.workflow.teams.items():
            # Create team
            team = Team(name=name)
            
            # Add lead if specified
            if config.lead:
                await team.add_member(config.lead, role=TeamRole.LEAD)
            
            # Add members
            for member_name in config.members:
                await team.add_member(member_name)
            
            # Add tools
            for tool_name in config.tools:
                if tool_name in self.tools:
                    await team.add_tool(self.tools[tool_name])
                else:
                    self.logger.error(f"Tool {tool_name} not found")
            self.teams[name] = team
            self.app.register_team(name, team)
        
        # Setup magnetic field
        if self.app_config.workflow:
            field = MagneticField(name=self.app.name)
            
            # Add attractions (push flow)
            for source, target in self.app_config.workflow.attractions:
                await field.process_team_flow(source, target, None, "->")
            
            # Add repulsions    
            for source, target in self.app_config.workflow.repulsions:
                await field.process_team_flow(source, target, None, "<>")
                
            # Add pulls (as fallback)
            for target, source in self.app_config.workflow.pulls:
                await field.process_team_flow(target, source, None, "<-")
            
            self.app.set_magnetic_field(field)

async def execute_glue_app(app_config: GlueAppConfig) -> GlueApp:
    """Execute GLUE application
    
    Args:
        app_config: The GLUE application configuration
        
    Returns:
        GlueApp: The configured and running application instance
    """
    executor = GlueExecutor(app_config)
    return await executor.execute()
