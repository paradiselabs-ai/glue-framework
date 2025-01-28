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
        
    def _convert_tool(self, glue_tool: AdhesiveTool) -> Any:
        """Convert a GLUE tool to a SmoLAgents tool"""
        @tool
        async def smol_tool(*args, **kwargs):
            """Wrapper for GLUE tool with enhanced documentation"""
            return await glue_tool.execute(*args, **kwargs)
            
        # Enhanced documentation with examples and usage patterns
        doc = f"""
        {glue_tool.description}

        Usage:
        <think>Explain why you need this tool</think>
        <tool>{glue_tool.name}</tool>
        <input>what you want the tool to do</input>

        Examples:
        1. Web Search:
        <think>I need to search for recent news about AI</think>
        <tool>web_search</tool>
        <input>latest developments in open source AI models</input>

        2. File Handler:
        <think>I need to save this information</think>
        <tool>file_handler</tool>
        <input>Title: AI News Summary
        Latest developments in open source AI:
        1. ...
        2. ...</input>

        3. Code Interpreter:
        <think>I need to analyze some data with Python</think>
        <tool>code_interpreter</tool>
        <input>
        import pandas as pd
        data = {'Model': ['GPT-4', 'Claude', 'Llama'],
                'Score': [95, 92, 88]}
        df = pd.DataFrame(data)
        print(f"Average score: {df['Score'].mean()}")
        </input>

        Notes:
        - Always explain your reasoning in <think> tags
        - Be specific about what you want the tool to do
        - Check tool results before proceeding
        """
            
        # Copy metadata with enhanced docs
        smol_tool.__name__ = glue_tool.name
        smol_tool.__doc__ = doc
        
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
