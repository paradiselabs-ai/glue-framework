"""GLUE Application Core"""

import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from .context import ContextState, ComplexityLevel

from .team import Team
from .model import Model
from .conversation import ConversationManager
from .memory import MemoryManager
from .workspace import WorkspaceManager
from .group_chat import GroupChatManager
from .state import StateManager
from .logger import get_logger
from ..tools.dynamic_tool_factory import DynamicToolFactory, ToolSpec, MCPServerSpec
from ..magnetic.field import MagneticField

@dataclass
class AppConfig:
    """Configuration for GLUE application"""
    name: str
    memory_limit: int = 1000  # Maximum number of memory segments to store (conversations, tool results, etc.)
    enable_persistence: bool = False  # Whether to persist memory between runs
    development: bool = False  # Enable development mode with additional logging
    sticky: bool = False  # Keep workspace between runs
    config: Dict[str, Any] = None  # Additional provider-specific configuration

class GlueApp:
    """Core GLUE application"""
    
    def __init__(
        self,
        name: str,
        config: AppConfig,
        workspace_dir: Optional[Path] = None
    ):
        self.name = name
        self.config = config
        self.logger = get_logger()
        
        # Core components
        self.teams: Dict[str, Team] = {}
        self.models: Dict[str, Model] = {}
        self.tools: Dict[str, Any] = {}  # Store initialized tools
        self.conversation_manager = ConversationManager(
            sticky=config.sticky,
            workspace_dir=str(workspace_dir) if workspace_dir else None
        )
        self.memory_manager = MemoryManager()
        self.workspace_manager = WorkspaceManager(workspace_dir)
        self.state_manager = StateManager()

        # Tool registry
        self._tool_registry: Dict[str, Any] = {}  # Persistent tool storage
        
        # Team communication
        self.group_chat_manager = GroupChatManager(name)
        self.magnetic_field = MagneticField(name)
        
        # Dynamic tool creation
        self.tool_factory = DynamicToolFactory()
        
    async def process_prompt(self, prompt: str) -> str:
        """Process user prompt with clear workflow status"""
        # Log prompt with separator for easy scanning of logs
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"New Prompt: {prompt}")
        self.logger.info(f"{'='*50}")
        
        try:
            # First check for tool/MCP creation request
            if any(keyword in prompt.lower() for keyword in ["create", "make", "build"]):
                if any(keyword in prompt.lower() for keyword in ["tool", "mcp", "server"]):
                    # Get relevant team based on prompt context
                    team = self._get_relevant_team(prompt)
                    
                    # Try to create tool/server
                    result = await self.tool_factory.parse_natural_request(prompt, team)
                    if result:
                        if isinstance(result, dict):
                            # MCP server created
                            tools = ", ".join(result.keys())
                            return f"Created MCP server with tools: {tools}"
                        else:
                            # Single tool created
                            return f"Created tool: {result.name}"
            
            # Check for tool enhancement request
            elif any(keyword in prompt.lower() for keyword in ["enhance", "improve", "upgrade"]):
                for tool_name in self.tool_factory.list_tools():
                    if tool_name.lower() in prompt.lower():
                        team = self._get_relevant_team(prompt)
                        enhanced_tool = await self.tool_factory.enhance_tool(
                            tool_name,
                            prompt,
                            team
                        )
                        return f"Enhanced tool: {enhanced_tool.name}"
            
            # Process normal prompt through teams
            team = self._get_relevant_team(prompt)
            if team:
                self.logger.info(f"Routing to team: {team.name}")
                self.logger.info(f"Team tools: {list(team.tools.keys()) if team.tools else 'None'}")
                
                # Get team's lead model
                lead_model = self.models.get(team.lead)
                if lead_model:
                    self.logger.info(f"Team lead: {lead_model.name}")
                    # Analyze context properly
                    context = self.conversation_manager.context_analyzer.analyze(
                        prompt,
                        available_tools=list(team.tools.keys()) if team.tools else None
                    )
                    
                    # Log context analysis
                    self.logger.info(f"Context Analysis:")
                    self.logger.info(f"- Complexity: {context.complexity}")
                    self.logger.info(f"- Tools Required: {list(context.tools_required) if context.tools_required else 'None'}")
                    self.logger.info(f"- Persistence: {context.requires_persistence}")
                    self.logger.info(f"- Memory: {context.requires_memory}")
                    self.logger.info(f"- Magnetic Flow: {context.magnetic_flow}")
                    
                    try:
                        # Process through conversation manager
                        response = await self.conversation_manager.process(
                            models={team.lead: lead_model},
                            user_input=prompt,
                            tools=team.tools,
                            context=context
                        )
                    except Exception as e:
                        # Fallback to direct model processing
                        self.logger.debug(f"Conversation manager failed: {str(e)}, falling back to direct processing")
                        response = await lead_model.process(prompt)
                    
                    # Store in memory with proper key
                    key = f"interaction_{datetime.now().timestamp()}"
                    await self.memory_manager.store(
                        key=key,
                        content={
                            "prompt": prompt,
                            "response": response,
                            "team": team.name
                        },
                        context=context
                    )
                    
                    return response
            
            return "No team available to process prompt"
            
        except Exception as e:
            self.logger.error(f"Error processing prompt: {str(e)}")
            raise
            
    def _get_relevant_team(self, prompt: str) -> Optional[Team]:
        """Get most relevant team based on prompt context"""
        # Check for explicit team mentions
        for team_name, team in self.teams.items():
            if team_name.lower() in prompt.lower():
                return team
                
        # Check for model mentions
        for model_name, model in self.models.items():
            if model_name.lower() in prompt.lower():
                # Find team containing this model
                for team in self.teams.values():
                    if model_name == team.lead or model_name in team.members:
                        return team
                        
        # Check for tool mentions
        for team in self.teams.values():
            for tool_name in team.tools:
                if tool_name.lower() in prompt.lower():
                    return team
                    
        # Default to first team if none found
        return next(iter(self.teams.values())) if self.teams else None
        
    def register_team(self, name: str, team: Team) -> None:
        """Register team with app (sync version for executor)"""
        self.teams[name] = team
        
    async def add_team(self, team: Team) -> None:
        """Add team to app (async version for runtime)"""
        self.teams[team.name] = team
        await self.magnetic_field.add_team(team)
        
    def register_model(self, name: str, model: Model) -> None:
        """Register model with app (sync version for executor)"""
        self.models[name] = model
        self.group_chat_manager.add_model(model)
        
    async def add_model(self, model: Model) -> None:
        """Add model to app (async version for runtime)"""
        self.models[model.name] = model
        self.group_chat_manager.add_model(model)
        
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up app resources")
        
        try:
            # Clean up core components
            await self.conversation_manager.cleanup()
            await self.memory_manager.cleanup()
            await self.workspace_manager.cleanup()
            await self.state_manager.cleanup()
            
            # Clean up team communication
            await self.group_chat_manager.cleanup()
            await self.magnetic_field.cleanup()
            
            # Clean up dynamic tools
            await self.tool_factory.cleanup()
            
            # Clean up teams
            for team in self.teams.values():
                await team.cleanup()
                
            # Clean up models
            for model in self.models.values():
                await model.cleanup()
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            raise
