"""SmolAgents Tool Executor with Enhanced Validation, Logging and Prefect Integration"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from prefect import task, flow
import logging
from pydantic import BaseModel, Field

from ..core.pydantic_models import (
    ToolResult, SmolAgentsTool, PrefectTaskConfig
)
from ..core.types import AdhesiveType
from ..core.logger import get_logger
from ..tools.base import BaseTool

logger = get_logger("executor")

class ToolIntent(BaseModel):
    """Validated tool usage intent from natural language"""
    tool_name: str = Field(..., description="Name of the tool to execute")
    input_data: Any = Field(..., description="Input data for the tool")
    adhesive: AdhesiveType = Field(..., description="Type of adhesive binding")
    description: Optional[str] = Field(None, description="Optional tool description")
    prefect_config: Optional[PrefectTaskConfig] = Field(None, description="Optional Prefect task configuration")

class SmolAgentsToolExecutor:
    """Core tool execution engine using SmolAgents with Prefect integration"""
    
    def __init__(self, team: Any, available_adhesives: set[AdhesiveType]):
        self.team = team
        self.available_adhesives = available_adhesives
        self._dynamic_tools: Dict[str, SmolAgentsTool] = {}
        logger.debug(f"Initialized tool executor for team {team} with adhesives {available_adhesives}")
        
    @flow(name="execute_tool")
    async def execute(self, model_response: str) -> Union[ToolResult, str]:
        """Execute tools based on natural language intent with Prefect orchestration"""
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
            
            try:
                # Execute tool with Prefect task
                logger.debug(f"Executing {intent.tool_name} with input: {intent.input_data}")
                result = await self._execute_tool_task(tool, intent)
                logger.debug(f"Tool execution successful: {str(result)[:100]}...")
                
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

    @task(retries=3)
    async def _execute_tool_task(self, tool: SmolAgentsTool, intent: ToolIntent) -> Any:
        """Execute tool with Prefect task configuration"""
        config = intent.prefect_config or PrefectTaskConfig()
        
        @task(
            name=f"execute_{tool.name}",
            retries=config.max_retries,
            retry_delay_seconds=config.retry_delay_seconds,
            timeout_seconds=config.timeout_seconds,
            tags=config.tags
        )
        async def execute():
            return await tool.forward_func(intent.input_data)
            
        return await execute()
        
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
                    description=parsed.get("description"),
                    prefect_config=parsed.get("prefect_config")
                )
                logger.debug(f"Successfully parsed intent: {intent}")
                return intent
            except Exception as e:
                logger.error(f"Invalid tool intent format: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse tool intent: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to parse tool intent: {str(e)}")
            
    @task
    async def _get_or_create_tool(self, intent: ToolIntent) -> Optional[SmolAgentsTool]:
        """Get existing tool or create new one dynamically with validation"""
        logger.debug(f"Getting or creating tool: {intent.tool_name}")
        
        # Check team tools first
        if intent.tool_name in self.team.tools:
            logger.debug(f"Found existing team tool: {intent.tool_name}")
            tool = self.team.tools[intent.tool_name]
            return self._wrap_as_smol_tool(tool, intent.description)
            
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
        
    def _wrap_as_smol_tool(self, tool: BaseTool, description: Optional[str] = None) -> SmolAgentsTool:
        """Wrap a BaseTool as a SmolAgentsTool"""
        return SmolAgentsTool(
            name=tool.name,
            description=description or tool.description,
            inputs=tool.inputs,
            output_type=tool.output_type,
            forward_func=tool.execute
        )
        
    @task
    async def _create_dynamic_tool(self, name: str, description: str) -> SmolAgentsTool:
        """Create a new tool dynamically using SmolAgents with validation"""
        try:
            # Create tool using SmolAgents
            from smolagents import create_tool
            logger.debug(f"Creating tool with SmolAgents: {name}")
            
            smol_tool = await create_tool(name=name, description=description)
            
            # Create SmolAgentsTool wrapper
            tool = SmolAgentsTool(
                name=name,
                description=description,
                inputs=smol_tool.inputs,
                output_type=smol_tool.output_type,
                forward_func=smol_tool.forward
            )
            
            # Store in dynamic tools
            self._dynamic_tools[name] = tool
            logger.info(f"Successfully created and stored dynamic tool: {name}")
            
            return tool
            
        except Exception as e:
            logger.error(f"Failed to create dynamic tool: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to create dynamic tool: {str(e)}")
            
    @task
    async def create_mcp_tool(self, server_name: str, tool_name: str) -> SmolAgentsTool:
        """Create a tool from an MCP server with validation"""
        logger.debug(f"Creating MCP tool: {server_name}/{tool_name}")
        
        try:
            # Get and validate tool schema from MCP
            schema = await self._get_mcp_schema(server_name, tool_name)
            if not isinstance(schema, dict) or "description" not in schema:
                raise ValueError("Invalid MCP tool schema")
            
            # Create SmolAgentsTool that wraps MCP
            tool = SmolAgentsTool(
                name=f"{server_name}_{tool_name}",
                description=schema.get("description", "MCP Tool"),
                inputs=schema.get("inputs", {}),
                output_type=schema.get("output_type", "string"),
                forward_func=lambda x: self._execute_mcp_tool(server_name, tool_name, x)
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
        from ..core.mcp import get_mcp_tool_schema
        return await get_mcp_tool_schema(server, tool)
        
    async def _execute_mcp_tool(self, server: str, tool: str, input_data: Any) -> Any:
        """Execute an MCP tool"""
        logger.debug(f"Executing MCP tool {server}/{tool}")
        from ..core.mcp import execute_mcp_tool
        return await execute_mcp_tool(server, tool, input_data)
