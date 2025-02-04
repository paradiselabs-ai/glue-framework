"""SmolAgents Provider Implementation

This provider uses SmolAgents to:
1. Create tools dynamically
2. Parse natural language into tool intents
3. Execute tools with proper adhesive bindings
4. Handle MCP tool integration
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from .base import BaseProvider
from ..core.types import AdhesiveType, ToolResult
from ..tools.base import BaseTool

class SmolAgentsProvider(BaseProvider):
    """Provider that uses SmolAgents for enhanced tool capabilities"""
    
    def __init__(
        self,
        name: str,
        team: str,
        available_adhesives: set[AdhesiveType],
        api_key: str,
        config: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            name=name,
            provider="smolagents",
            team=team,
            available_adhesives=available_adhesives,
            api_key=api_key,
            config=config
        )
        self.base_url = base_url
        self._dynamic_tools: Dict[str, BaseTool] = {}
        
    async def create_tool(self, name: str, description: str, function: Any) -> BaseTool:
        """Create a new tool on the fly"""
        from smolagents import tool
        
        # Convert to SmolAgents tool
        @tool
        async def dynamic_tool(*args, **kwargs):
            return await function(*args, **kwargs)
            
        # Create tool instance
        tool = BaseTool(
            name=name,
            description=description,
            execute=dynamic_tool
        )
        
        # Add to team's tools
        await self.team.add_tool(tool)
        
        # Store in dynamic tools
        self._dynamic_tools[name] = tool
        
        return tool
        
    async def create_mcp_tool(self, server_name: str, tool_name: str) -> BaseTool:
        """Create tool from MCP server"""
        from smolagents import tool
        
        # Get tool schema from MCP
        schema = await self._get_mcp_schema(server_name, tool_name)
        
        # Create SmolAgents tool that uses MCP
        @tool
        async def mcp_tool(*args, **kwargs):
            return await self._use_mcp_tool(
                server_name=server_name,
                tool_name=tool_name,
                arguments=kwargs
            )
            
        # Create tool instance
        tool = BaseTool(
            name=f"{server_name}_{tool_name}",
            description=schema.get("description", "MCP Tool"),
            execute=mcp_tool
        )
        
        # Add to team's tools
        await self.team.add_tool(tool)
        
        # Store in dynamic tools
        self._dynamic_tools[tool.name] = tool
        
        return tool
        
    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use tool with enhanced execution"""
        # Validate adhesive and tool
        if adhesive not in self.available_adhesives:
            raise ValueError(f"Model {self.name} cannot use {adhesive.name} adhesive")
            
        # Get tool from team
        tool = self.team.tools.get(tool_name)
        if not tool:
            # Check dynamic tools
            tool = self._dynamic_tools.get(tool_name)
            if not tool:
                raise ValueError(f"Tool {tool_name} not available to team {self.team.name}")
                
        # Import team data if using GLUE
        if adhesive == AdhesiveType.GLUE:
            if hasattr(tool, 'import_team_data'):
                await tool.import_team_data(self.team.shared_results.get(tool_name))
                
        # Execute through SmolAgents
        from smolagents import SmolAgent
        agent = SmolAgent()
        smol_tool = await self._convert_tool(tool)
        result = await agent.execute_tool(smol_tool, input_data)
        
        # Create result
        tool_result = ToolResult(
            tool_name=tool_name,
            result=result,
            adhesive=adhesive,
            timestamp=datetime.now()
        )
        
        # Handle based on adhesive
        if adhesive == AdhesiveType.GLUE:
            await self.team.share_result(tool_result)
        elif adhesive == AdhesiveType.VELCRO:
            self._session_results[tool_name] = tool_result
            
        return tool_result
        
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to SmolAgents"""
        try:
            from smolagents import SmolAgent
            agent = SmolAgent()
            
            # Process request through SmolAgents
            response = await agent.process_request(
                messages=request_data["messages"],
                tools=list(self.team.tools.values()),
                adhesives=[a.name for a in self.available_adhesives]
            )
            
            return response
            
        except Exception as e:
            raise ValueError(f"Failed to make request: {str(e)}")
            
    async def _handle_error(self, error: Exception) -> None:
        """Handle SmolAgents errors"""
        # Log the error
        print(f"SmolAgents error: {str(error)}")
        # Re-raise as provider error
        raise ValueError(f"SmolAgents error: {str(error)}")
        
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare request with SmolAgents context"""
        # Get natural context
        workspace_context = self._format_workspace()
        team_context = self._format_team_context()
        conversation_context = self._format_conversation()
        
        # Create system prompt that encourages natural tool usage
        system_prompt = f"""You are {self.name}, working in the {self.team} team.

Your role: {self.role}

Your workspace:
{workspace_context}

Your team:
{team_context}

Recent conversation:
{conversation_context}

You can use tools naturally by describing what you want to do. For example:
- "Let me search for information about that topic"
- "I'll save these findings to a file"
- "I need to analyze this data"

When using tools, be clear about your intentions:
- Share with team (GLUE): "I'll search for this and share it with the team"
- Keep for session (VELCRO): "I'll save this for my reference"
- One-time use (TAPE): "Let me quickly check something"

You can also request new tools if needed:
- "I need a tool that can format text in APA style"
- "Could we create a tool to analyze sentiment?"

Available Tools:
{workspace_context}"""

        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process response and execute any tool intents"""
        try:
            content = response["choices"][0]["message"]["content"]
            
            # Parse natural language into tool intent
            from smolagents import SmolAgent
            agent = SmolAgent()
            
            # Try to parse tool intent
            try:
                intent = await agent.parse_intent(
                    content,
                    available_tools=list(self.team.tools.keys()),
                    available_adhesives=[a.name for a in self.available_adhesives]
                )
                
                if intent:
                    # Execute tool
                    result = await self.use_tool(
                        tool_name=intent["tool"],
                        adhesive=AdhesiveType[intent.get("adhesive", "TAPE").upper()],
                        input_data=intent["input"]
                    )
                    return str(result.result)
                    
            except Exception as e:
                # If tool execution fails, return original response
                pass
                
            return content
            
        except Exception as e:
            raise ValueError(f"Failed to process response: {str(e)}")
            
    async def _convert_tool(self, tool: BaseTool) -> Any:
        """Convert GLUE tool to SmolAgents tool"""
        from smolagents import tool as smol_tool
        
        @smol_tool
        async def converted_tool(*args, **kwargs):
            return await tool.execute(*args, **kwargs)
            
        converted_tool.name = tool.name
        converted_tool.description = tool.description
        
        return converted_tool
            
    async def _get_mcp_schema(self, server: str, tool: str) -> Dict[str, Any]:
        """Get tool schema from MCP server"""
        from ..tools.executor import SmolAgentsToolExecutor
        executor = SmolAgentsToolExecutor(self.team, self.available_adhesives)
        return await executor._get_mcp_schema(server, tool)
        
    async def _use_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Use MCP tool through SmolAgents"""
        from ..tools.executor import SmolAgentsToolExecutor
        executor = SmolAgentsToolExecutor(self.team, self.available_adhesives)
        return await executor.create_mcp_tool(server_name, tool_name)
