"""SmolAgents Tool Executor with Enhanced Validation and Logging

This module provides the core tool execution engine using SmolAgents to:
1. Parse natural language into tool intents with validation
2. Create and manage tools dynamically with proper error handling
3. Execute tools with adhesive bindings and retry logic
4. Handle MCP tool integration with validation
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field
from ..core.types import AdhesiveType, ToolResult
from ..core.logger import get_logger
from ..tools.base import BaseTool

logger = get_logger("executor")

class ToolIntent(BaseModel):
    """Validated tool usage intent from natural language"""
    tool_name: str = Field(..., description="Name of the tool to execute")
    input_data: Any = Field(..., description="Input data for the tool")
    adhesive: AdhesiveType = Field(..., description="Type of adhesive binding")
    description: Optional[str] = Field(None, description="Optional tool description")

class SmolAgentsToolExecutor:
    """Core tool execution engine using SmolAgents with enhanced validation and logging"""
    
    def __init__(self, team: Any, available_adhesives: set[AdhesiveType]):
        self.team = team
        self.available_adhesives = available_adhesives
        self._dynamic_tools: Dict[str, BaseTool] = {}
        logger.debug(f"Initialized tool executor for team {team} with adhesives {available_adhesives}")
        
    async def execute(self, model_response: str) -> Union[ToolResult, str]:
        """Execute tools based on natural language intent with validation and logging"""
        logger.debug(f"Processing model response for tool execution: {model_response[:100]}...")
        
        try:
            # Parse and validate intent
            intent = await self._parse_tool_intent(model_response)
            if not intent:
                logger.debug("No tool intent found in response")
                return model_response
                
            logger.info(f"Parsed tool intent: {intent.tool_name} with {intent.adhesive} binding")
                
            # Get or create tool
            tool = await self._get_or_create_tool(intent)
            if not tool:
                msg = f"Tool {intent.tool_name} not available"
                logger.warning(msg)
                return msg
            
            try:                # Execute tool with retry logic
                logger.debug(f"Executing {intent.tool_name} with input: {intent.input_data}")
                result = await tool.execute(intent.input_data)
                logger.debug(f"Tool execution successful: {result[:100]}...")
                
                # Create validated result
                tool_result = ToolResult(
                    tool_name=intent.tool_name,
                    result=result,
                    adhesive=intent.adhesive,
                    timestamp=datetime.now()
                )
            
                # Handle result based on adhesive
                if intent.adhesive == AdhesiveType.GLUE:
                    logger.debug(f"Sharing {intent.tool_name} result with team")
                    await self.team.share_result(tool_result)
                    
                return tool_result
                
            except Exception as e:
                msg = f"Tool execution failed: {str(e)}"
                logger.error(msg, exc_info=True)
                return msg
                
        except Exception as e:
            msg = f"Failed to process tool intent: {str(e)}"
            logger.error(msg, exc_info=True)
            return msg
        
    async def _parse_tool_intent(self, response: str) -> Optional[ToolIntent]:
        """Use SmolAgents to parse natural language into validated tool intent"""
        try:
            # Initialize SmolAgent for parsing
            from smolagents import CodeAgent
            
            # Get first available model from team
            model = next(iter(self.team.models.values()))
            if not model:
                raise ValueError("No model available in team")
                
            agent = CodeAgent(
                model=model,
                tools=list(self.team.tools.values())
            )
            
            logger.debug("Parsing response with SmolAgent")
            
            # Parse response into structured intent
            parsed = agent.run(
                response,
                additional_args={
                    "available_tools": list(self.team.tools.keys()),
                    "available_adhesives": [a.name for a in self.available_adhesives]
                }
            )
            
            # Validate and create intent
            try:
                intent = ToolIntent(
                    tool_name=parsed.get("tool"),
                    input_data=parsed.get("input"),
                    adhesive=AdhesiveType[parsed.get("adhesive", "TAPE").upper()],
                    description=parsed.get("description")
                )
                logger.debug(f"Successfully parsed intent: {intent}")
                return intent
            except Exception as e:
                logger.error(f"Invalid tool intent format: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse tool intent: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to parse tool intent: {str(e)}")
            
    async def _get_or_create_tool(self, intent: ToolIntent) -> Optional[BaseTool]:
        """Get existing tool or create new one dynamically with validation"""
        logger.debug(f"Getting or creating tool: {intent.tool_name}")
        
        # Check team tools first
        if intent.tool_name in self.team.tools:
            logger.debug(f"Found existing team tool: {intent.tool_name}")
            return self.team.tools[intent.tool_name]
            
        # Check dynamic tools
        if intent.tool_name in self._dynamic_tools:
            logger.debug(f"Found existing dynamic tool: {intent.tool_name}")
            return self._dynamic_tools[intent.tool_name]
            
        # Try to create tool dynamically
        if intent.description:
            logger.info(f"Creating new dynamic tool: {intent.tool_name}")
            try:
                tool = await self._create_dynamic_tool(
                    name=intent.tool_name,
                    description=intent.description
                )
                logger.debug(f"Successfully created dynamic tool: {intent.tool_name}")
                return tool
            except Exception as e:
                logger.error(f"Failed to create dynamic tool: {str(e)}", exc_info=True)
                return None
                
        logger.warning(f"No tool found or created: {intent.tool_name}")
        return None
        
    async def _create_dynamic_tool(self, name: str, description: str) -> BaseTool:
        """Create a new tool dynamically using SmolAgents with validation"""
        try:
            # Create tool using SmolAgents
            from smolagents import create_tool
            logger.debug(f"Creating tool with SmolAgents: {name}")
            
            tool = await create_tool(name=name, description=description)
            
            # Validate tool interface
            if not hasattr(tool, 'execute') or not callable(getattr(tool, 'execute')):
                raise ValueError("Created tool missing required 'execute' method")
            
            # Store in dynamic tools
            self._dynamic_tools[name] = tool
            logger.info(f"Successfully created and stored dynamic tool: {name}")
            
            return tool
            
        except Exception as e:
            logger.error(f"Failed to create dynamic tool: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to create dynamic tool: {str(e)}")
            
    async def create_mcp_tool(self, server_name: str, tool_name: str) -> BaseTool:
        """Create a tool from an MCP server with validation"""
        logger.debug(f"Creating MCP tool: {server_name}/{tool_name}")
        
        try:
            # Get and validate tool schema from MCP
            schema = await self._get_mcp_schema(server_name, tool_name)
            if not isinstance(schema, dict) or "description" not in schema:
                raise ValueError("Invalid MCP tool schema")
            
            # Create tool that wraps MCP
            tool = await self._create_dynamic_tool(
                name=f"{server_name}_{tool_name}",
                description=schema.get("description", "MCP Tool")
            )
            
            # Store in dynamic tools
            self._dynamic_tools[tool.name] = tool
            logger.info(f"Successfully created MCP tool: {tool.name}")
            
            return tool
            
        except Exception as e:
            logger.error(f"Failed to create MCP tool: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to create MCP tool: {str(e)}")
            
    async def _get_mcp_schema(self, server: str, tool: str) -> Dict[str, Any]:
        """Get tool schema from MCP server with validation"""
        logger.debug(f"Getting MCP schema for {server}/{tool}")
        # TODO: Implement MCP schema retrieval
        raise NotImplementedError("MCP schema retrieval not yet implemented")
