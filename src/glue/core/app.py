"""GLUE Application Core"""

import asyncio
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
# from dataclasses import dataclass  <- Remove dataclass import
from datetime import datetime

from .context import ContextState, ComplexityLevel

from .team import Team
from .model import Model
from .conversation import ConversationManager
from .memory import MemoryManager
from .workspace import WorkspaceManager
from .group_chat import GroupChatManager
from .state import StateManager
from loguru import logger
from .orchestrator import GlueOrchestrator
from ..tools.dynamic_tool_factory import DynamicToolFactory, ToolSpec, MCPServerSpec
from ..magnetic.field_pydantic import MagneticField

from pydantic import BaseModel, Field  # Import Pydantic


class AppConfig(BaseModel):
    """Configuration for GLUE application"""
    name: str
    memory_limit: int = Field(1000, description="Maximum number of memory segments to store (conversations, tool results, etc.)")
    enable_persistence: bool = Field(False, description="Whether to persist memory between runs")
    development: bool = Field(False, description="Enable development mode with additional logging")
    sticky: bool = Field(False, description="Keep workspace between runs")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific configuration")  # Use default_factory for mutable defaults


class ToolSpec(BaseModel):
    """Specification for a tool"""
    name: str
    description: str
    parameters: Dict[str, str]


class GlueApp:
    """Core GLUE application"""
    
    def __init__(
        self,
        name: str,
        config: AppConfig,  # Use the Pydantic model
        workspace_dir: Optional[Path] = None
    ):
        self.name = name
        self.config = config
        logger.add("glue_app.log", rotation="10 MB") # Add file handler
        
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
        
        # Team communication and orchestration
        self.group_chat_manager = GroupChatManager(name)
        self.magnetic_field = MagneticField(name)
        self.orchestrator = GlueOrchestrator()
        
        # Dynamic tool creation
        self.tool_factory = DynamicToolFactory()
        
    async def process_prompt(self, prompt: str) -> str:
        """Process user prompt with orchestrated workflow"""
        # Log prompt
        logger.info(f"\n{'='*50}")
        logger.info(f"New Prompt: {prompt}")
        logger.info(f"{'='*50}")
        
        try:
            # Handle tool/MCP creation requests
            if self._is_tool_request(prompt):
                return await self._handle_tool_request(prompt)
                
            # Get app context for orchestrator
            context = await self._prepare_context(prompt)
            
            # Let orchestrator handle execution
            response = await self.orchestrator.execute_prompt(prompt, context)
            
            # Store in memory
            await self._store_interaction(prompt, response, context)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing prompt: {str(e)}")
            raise
            
    def _is_tool_request(self, prompt: str) -> bool:
        """Check if prompt is requesting tool creation/enhancement"""
        creation_keywords = ["create", "make", "build"]
        tool_keywords = ["tool", "mcp", "server"]
        enhance_keywords = ["enhance", "improve", "upgrade"]
        
        is_creation = any(kw in prompt.lower() for kw in creation_keywords)
        is_tool = any(kw in prompt.lower() for kw in tool_keywords)
        is_enhancement = any(kw in prompt.lower() for kw in enhance_keywords)
        
        return (is_creation and is_tool) or is_enhancement
        
    async def _handle_tool_request(self, prompt: str) -> str:
        """Handle tool creation/enhancement requests"""
        team = self._get_relevant_team(prompt)
        
        if any(kw in prompt.lower() for kw in ["create", "make", "build"]):
            result = await self.tool_factory.parse_natural_request(prompt, team)
            if isinstance(result, dict):
                tools = ", ".join(result.keys())
                return f"Created MCP server with tools: {tools}"
            return f"Created tool: {result.name}"
            
        # Must be enhancement
        for tool_name in self.tool_factory.list_tools():
            if tool_name.lower() in prompt.lower():
                enhanced = await self.tool_factory.enhance_tool(tool_name, prompt, team)
                return f"Enhanced tool: {enhanced.name}"
                
        return "Could not understand tool request."
        
    async def _prepare_context(self, prompt: str) -> Dict[str, Any]:
        """Prepare context for orchestrator"""
        # Analyze context
        context = self.conversation_manager.context_analyzer.analyze(
            prompt,
            available_tools=self._get_available_tools()
        )
        
        # Log analysis
        self._log_context_analysis(context)
        
        # Prepare orchestrator context
        return {
            "teams": self.teams,
            "models": self.models,
            "tools": self._get_team_tools(),
            "adhesives": self._get_model_adhesives(),
            "context": context,
            "memory": self.memory_manager,
            "workspace": self.workspace_manager
        }
        
    def _get_available_tools(self) -> List[str]:
        """Get all available tools across teams"""
        tools = set()
        for team in self.teams.values():
            tools.update(team.tools.keys())
        return list(tools)
        
    def _get_team_tools(self) -> Dict[str, Set[str]]:
        """Get tool mapping for each team"""
        return {
            team.name: set(team.tools.keys())
            for team in self.teams.values()
        }
        
    def _get_model_adhesives(self) -> Dict[str, Set[str]]:
        """Get adhesive types for each model"""
        return {
            model.name: model.available_adhesives
            for model in self.models.values()
        }
        
    def _log_context_analysis(self, context: ContextState) -> None:
        """Log context analysis results"""
        logger.info(f"Context Analysis:")
        logger.info(f"- Complexity: {context.complexity}")
        logger.info(f"- Tools Required: {list(context.tools_required) if context.tools_required else 'None'}")
        logger.info(f"- Persistence: {context.requires_persistence}")
        logger.info(f"- Memory: {context.requires_memory}")
        logger.info(f"- Magnetic Flow: {context.magnetic_flow}")
        
    async def _store_interaction(
        self,
        prompt: str,
        response: str,
        context: Dict[str, Any]
    ) -> None:
        """Store interaction in memory"""
        try:
            # Atomic capture of references
            memory_manager: Optional[MemoryManager] = self.memory_manager
            context_context = context.get("context") if context else None
            
            if not memory_manager or not context_context:
                logger.warning(f"Skipping storage - memory_manager: {bool(memory_manager)}, context: {bool(context_context)}")
                return

            key = f"interaction_{datetime.now().timestamp()}"
            await memory_manager.store(
                key=key,
                content={
                    "prompt": prompt,
                    "response": response,
                    "context": context_context
                },
                context=context_context
            )
        except KeyError as e:
            logger.error(f"Missing context key: {str(e)}")
        except TypeError as e:
            logger.error(f"Invalid context type: {str(e)}")
        except Exception as e:
            logger.error(f"Error storing interaction: {str(e)}")
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
        self.orchestrator.register_team(team)  # Register with orchestrator
        
    async def add_team(self, team: Team) -> None:
        """Add team to app (async version for runtime)"""
        self.teams[team.name] = team
        self.orchestrator.register_team(team)  # Register with orchestrator
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
        logger.info("Cleaning up app resources")
        
        try:
            # Clean up core components
            await self.conversation_manager.cleanup()
            await self.memory_manager.cleanup()
            await self.workspace_manager.cleanup()
            await self.state_manager.cleanup()
            
            # Clean up team communication
            await self.group_chat_manager.cleanup()
            await self.magnetic_field.cleanup()
            
            # Clean up orchestrator
            # No cleanup needed - stateless
            
            # Clean up dynamic tools
            await self.tool_factory.cleanup()
            
            # Clean up teams
            for team in self.teams.values():
                await team.cleanup()
                
            # Clean up models
            for model in self.models.values():
                await model.cleanup()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            raise
