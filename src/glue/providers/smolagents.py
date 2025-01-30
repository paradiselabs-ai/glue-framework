"""SmoLAgents Provider Implementation"""

import os
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime

from smolagents import CodeAgent, ToolCallingAgent, HfApiModel, TransformersModel, LiteLLMModel, tool
from ..core.model import ModelConfig
from ..core.logger import get_logger
from ..core.types import AdhesiveType, ToolResult
from .base import BaseProvider
from ..adhesive.tool import AdhesiveTool

class SmoLAgentsProvider(BaseProvider):
    """
    Provider that uses SmoLAgents for execution.
    
    Features:
    - Support for both CodeAgent and ToolCallingAgent
    - Multiple model backends (HF, Transformers, LiteLLM)
    - Tool conversion between GLUE and SmoLAgents
    - Adhesive binding support
    """
    
    def __init__(
        self,
        name: str,
        provider: str,
        team: str,
        available_adhesives: Set[AdhesiveType],
        api_key: Optional[str] = None,
        config: Optional[ModelConfig] = None
    ):
        """Initialize SmoLAgents provider"""
        super().__init__(
            name=name,
            provider=provider,
            team=team,
            available_adhesives=available_adhesives,
            api_key=api_key,
            config=config
        )
        
        # Initialize logger
        self.logger = get_logger()
        
        # Set up agents - each model gets its own instances
        self._code_agent = CodeAgent()
        self._tool_agent = ToolCallingAgent()
        
        # Tool management
        self._tools: Dict[str, Any] = {}
        self._session_results: Dict[str, ToolResult] = {}  # VELCRO results
        
        self.logger.debug(f"Initialized SmoLAgents provider: {name}")
        
    async def create_tool(self, description: str) -> AdhesiveTool:
        """Create a new tool from natural language description"""
        # Use SmolAgents to create tool implementation
        @tool
        async def dynamic_tool(*args, **kwargs):
            """Dynamic tool created from description"""
            # Get tool name from first line
            name = description.split('\n')[0].strip().lower().replace(' ', '_')
            
            # Create SmolAgents tool
            agent = self._code_agent
            result = await agent.run(
                f"Create a tool that {description}\n"
                f"Input: {args[0] if args else kwargs}"
            )
            return result
            
        # Create GLUE tool wrapper
        tool = AdhesiveTool(
            name=description.split('\n')[0].strip().lower().replace(' ', '_'),
            description=description,
            execute=dynamic_tool
        )
        
        # Add to team's tools
        await self.team.add_tool(tool.name, tool)
        
        return tool
        
    async def create_mcp_tool(self, description: str) -> AdhesiveTool:
        """Create a new MCP tool from natural language description"""
        # Use SmolAgents to analyze description and create MCP tool
        agent = self._code_agent
        analysis = await agent.run(
            f"Analyze this tool request and determine:\n"
            f"1. Which MCP server to use\n"
            f"2. What tool to create\n"
            f"Request: {description}"
        )
        
        # Extract server and tool info
        server_name = analysis.get('server')
        tool_name = analysis.get('tool')
        
        # Create MCP tool
        @tool
        async def mcp_tool(*args, **kwargs):
            """MCP tool created from description"""
            return await use_mcp_tool(
                server_name=server_name,
                tool_name=tool_name,
                arguments=kwargs
            )
            
        # Create GLUE tool wrapper
        tool = AdhesiveTool(
            name=f"{server_name}_{tool_name}",
            description=description,
            execute=mcp_tool
        )
        
        # Add to team's tools
        await self.team.add_tool(tool.name, tool)
        
        return tool
        
    def _convert_tool(self, glue_tool: AdhesiveTool) -> Any:
        """Convert a GLUE tool to a SmolAgents tool"""
        @tool
        async def smol_tool(*args, **kwargs):
            """Wrapper for GLUE tool with enhanced documentation"""
            return await glue_tool.execute(*args, **kwargs)
            
        # Copy metadata
        smol_tool.__name__ = glue_tool.name
        smol_tool.__doc__ = glue_tool.description
        
        return smol_tool
        
    def _get_agent(self, tool_name: str):
        """Get appropriate agent based on tool type"""
        if tool_name == "code_interpreter":
            return self._code_agent
        return self._tool_agent
        
    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use a tool with specified adhesive type"""
        if adhesive not in self.available_adhesives:
            raise ValueError(f"Model {self.name} cannot use {adhesive.name} adhesive")
            
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not available")
            
        # Get appropriate agent
        agent = self._get_agent(tool_name)
        
        # Convert and execute tool
        tool = self._convert_tool(self._tools[tool_name])
        result = await agent.execute_tool(tool, input_data)
        
        # Create tool result
        tool_result = ToolResult(
            tool_name=tool_name,
            result=result,
            adhesive=adhesive,
            timestamp=datetime.now()
        )
        
        # Handle result based on adhesive
        if adhesive == AdhesiveType.GLUE:
            # Share with team - persists across sessions if app is sticky
            await self.team.share_result(tool_name, tool_result)
        elif adhesive == AdhesiveType.VELCRO:
            # Keep for this session only
            self._session_results[tool_name] = tool_result
        # TAPE results are just returned, no storage needed
            
        return tool_result
        
    async def generate(self, prompt: str) -> str:
        """Generate a response using appropriate agent"""
        # Use tool agent for general prompts
        result = await self._tool_agent.run(prompt)
        return str(result)
        
    async def cleanup(self) -> None:
        """Cleanup provider resources"""
        # Clear tool instances
        self._tools.clear()
        
        # Clear session results (VELCRO)
        # Note: GLUE results persist in team.shared_results if app is sticky
        # Session results are always cleared as they're session-specific
        self._session_results.clear()
