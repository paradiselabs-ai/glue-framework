"""MCP (Model Context Protocol) integration for GLUE framework"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from ..core.logger import get_logger

logger = get_logger("mcp")

class McpToolSchema(BaseModel):
    """Schema for an MCP tool"""
    name: str
    description: str
    inputs: Dict[str, Dict[str, Any]]
    output_type: str
    metadata: Dict[str, Any] = {}

async def get_mcp_tool_schema(server: str, tool: str) -> Dict[str, Any]:
    """Get tool schema from MCP server"""
    from mcp import use_mcp_tool
    
    try:
        # Get tool schema from MCP server
        schema = await use_mcp_tool(
            server_name=server,
            tool_name="get_tool_schema",
            arguments={"tool_name": tool}
        )
        
        # Validate schema
        validated = McpToolSchema(**schema)
        logger.debug(f"Got valid schema for {server}/{tool}")
        
        return validated.dict()
        
    except Exception as e:
        logger.error(f"Failed to get MCP schema for {server}/{tool}: {str(e)}")
        raise ValueError(f"Failed to get MCP schema: {str(e)}")

async def execute_mcp_tool(server: str, tool: str, input_data: Any) -> Any:
    """Execute a tool on an MCP server"""
    from mcp import use_mcp_tool
    
    try:
        # Execute tool
        logger.debug(f"Executing {server}/{tool} with input: {input_data}")
        result = await use_mcp_tool(
            server_name=server,
            tool_name=tool,
            arguments=input_data
        )
        logger.debug(f"Successfully executed {server}/{tool}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to execute MCP tool {server}/{tool}: {str(e)}")
        raise ValueError(f"Failed to execute MCP tool: {str(e)}")

async def list_mcp_tools(server: str) -> Dict[str, McpToolSchema]:
    """List available tools on an MCP server"""
    from mcp import use_mcp_tool
    
    try:
        # Get tool list
        tools = await use_mcp_tool(
            server_name=server,
            tool_name="list_tools",
            arguments={}
        )
        
        # Validate each tool schema
        validated = {
            name: McpToolSchema(**schema)
            for name, schema in tools.items()
        }
        
        logger.debug(f"Listed {len(validated)} tools from {server}")
        return {name: tool.dict() for name, tool in validated.items()}
        
    except Exception as e:
        logger.error(f"Failed to list MCP tools for {server}: {str(e)}")
        raise ValueError(f"Failed to list MCP tools: {str(e)}")

async def check_mcp_server(server: str) -> bool:
    """Check if an MCP server is available"""
    from mcp import use_mcp_tool
    
    try:
        # Try to ping server
        await use_mcp_tool(
            server_name=server,
            tool_name="ping",
            arguments={}
        )
        logger.debug(f"MCP server {server} is available")
        return True
        
    except Exception as e:
        logger.warning(f"MCP server {server} is not available: {str(e)}")
        return False

class McpServerConfig(BaseModel):
    """Configuration for an MCP server"""
    name: str
    command: str
    args: list[str] = []
    env: Dict[str, str] = {}
    auto_start: bool = False
    metadata: Dict[str, Any] = {}

async def start_mcp_server(config: McpServerConfig) -> bool:
    """Start an MCP server"""
    from mcp import start_server
    
    try:
        # Start server
        await start_server(
            command=config.command,
            args=config.args,
            env=config.env
        )
        logger.info(f"Started MCP server {config.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start MCP server {config.name}: {str(e)}")
        return False
