"""Dynamic Tool Factory for GLUE Framework

This module provides sophisticated tool creation capabilities that integrate
with SmolAgents while maintaining GLUE's team and adhesive mechanics.
"""

import asyncio
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass
from datetime import datetime

from ..core.types import AdhesiveType
from .base import BaseTool
from ..core.team import Team
from ..core.model import Model
from ..core.logger import get_logger

@dataclass
class ToolSpec:
    """Specification for tool creation"""
    name: str
    description: str
    inputs: Dict[str, Dict[str, Any]]
    output_type: str = "string"
    adhesive_types: List[AdhesiveType] = None
    team_name: Optional[str] = None

@dataclass
class MCPServerSpec:
    """Specification for MCP server creation"""
    name: str
    tools: List[ToolSpec]
    env_vars: Dict[str, str] = None
    base_url: Optional[str] = None

class DynamicToolFactory:
    """Factory for creating tools and MCP servers dynamically"""
    
    def __init__(self):
        self.logger = get_logger()
        self._dynamic_tools: Dict[str, BaseTool] = {}
        self._mcp_servers: Dict[str, Any] = {}
        
    async def create_tool_from_spec(
        self,
        spec: ToolSpec,
        team: Optional[Team] = None
    ) -> BaseTool:
        """Create a tool from specification"""
        from smolagents import SmolAgent, tool
        
        self.logger.info(f"Creating tool: {spec.name}")
        
        try:
            # Generate implementation using SmolAgents
            agent = SmolAgent()
            implementation = await agent.generate_tool_implementation(
                name=spec.name,
                description=spec.description,
                inputs=spec.inputs,
                output_type=spec.output_type
            )
            
            # Create tool instance
            @tool
            async def dynamic_tool(*args, **kwargs):
                return await implementation(*args, **kwargs)
            
            tool_instance = BaseTool(
                name=spec.name,
                description=spec.description,
                execute=dynamic_tool
            )
            
            # Add to team if provided
            if team:
                await team.add_tool(tool_instance)
                
            # Store in dynamic tools
            self._dynamic_tools[spec.name] = tool_instance
            
            self.logger.info(f"Successfully created tool: {spec.name}")
            return tool_instance
            
        except Exception as e:
            self.logger.error(f"Failed to create tool {spec.name}: {str(e)}")
            raise
            
    async def create_mcp_server_from_spec(
        self,
        spec: MCPServerSpec,
        team: Optional[Team] = None
    ) -> Dict[str, BaseTool]:
        """Create MCP server and its tools"""
        from smolagents import SmolAgent
        
        self.logger.info(f"Creating MCP server: {spec.name}")
        
        try:
            # Generate server implementation
            agent = SmolAgent()
            server_impl = await agent.generate_mcp_server(
                name=spec.name,
                tools=[{
                    "name": tool.name,
                    "description": tool.description,
                    "inputs": tool.inputs,
                    "output_type": tool.output_type
                } for tool in spec.tools]
            )
            
            # Create tools for each server endpoint
            tools = {}
            for tool_spec in spec.tools:
                tool = await self.create_tool_from_spec(tool_spec, team)
                tools[tool_spec.name] = tool
                
            # Store server
            self._mcp_servers[spec.name] = {
                "implementation": server_impl,
                "tools": tools,
                "spec": spec
            }
            
            self.logger.info(f"Successfully created MCP server: {spec.name}")
            return tools
            
        except Exception as e:
            self.logger.error(f"Failed to create MCP server {spec.name}: {str(e)}")
            raise
            
    async def parse_natural_request(
        self,
        request: str,
        team: Optional[Team] = None
    ) -> Union[BaseTool, Dict[str, BaseTool], None]:
        """Parse natural language tool creation request"""
        from smolagents import SmolAgent
        
        self.logger.info("Parsing tool creation request")
        
        try:
            agent = SmolAgent()
            intent = await agent.parse_tool_intent(request)
            
            if not intent:
                return None
                
            if intent.get("type") == "tool":
                # Create single tool
                spec = ToolSpec(
                    name=intent["name"],
                    description=intent["description"],
                    inputs=intent.get("inputs", {}),
                    output_type=intent.get("output_type", "string")
                )
                return await self.create_tool_from_spec(spec, team)
                
            elif intent.get("type") == "mcp":
                # Create MCP server with tools
                spec = MCPServerSpec(
                    name=intent["server_name"],
                    tools=[ToolSpec(
                        name=intent["tool_name"],
                        description=intent["description"],
                        inputs=intent.get("inputs", {}),
                        output_type=intent.get("output_type", "string")
                    )]
                )
                return await self.create_mcp_server_from_spec(spec, team)
                
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to parse tool request: {str(e)}")
            raise
            
    async def enhance_tool(
        self,
        tool_name: str,
        enhancement_request: str,
        team: Optional[Team] = None
    ) -> BaseTool:
        """Enhance existing tool based on natural language request"""
        from smolagents import SmolAgent
        
        self.logger.info(f"Enhancing tool: {tool_name}")
        
        try:
            # Get existing tool
            tool = self._dynamic_tools.get(tool_name)
            if not tool:
                raise ValueError(f"Tool {tool_name} not found")
                
            # Generate enhanced implementation
            agent = SmolAgent()
            enhanced_impl = await agent.enhance_tool_implementation(
                name=tool.name,
                description=tool.description,
                current_implementation=tool.execute,
                enhancement_request=enhancement_request
            )
            
            # Create enhanced tool
            enhanced_tool = await self.create_tool_from_spec(
                ToolSpec(
                    name=tool.name,
                    description=f"{tool.description} (Enhanced: {enhancement_request})",
                    inputs=tool.inputs,
                    output_type=tool.output_type
                ),
                team
            )
            
            # Replace old implementation
            self._dynamic_tools[tool_name] = enhanced_tool
            
            self.logger.info(f"Successfully enhanced tool: {tool_name}")
            return enhanced_tool
            
        except Exception as e:
            self.logger.error(f"Failed to enhance tool {tool_name}: {str(e)}")
            raise
            
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get dynamic tool by name"""
        return self._dynamic_tools.get(name)
        
    def get_mcp_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get MCP server by name"""
        return self._mcp_servers.get(name)
        
    def list_tools(self) -> List[str]:
        """List all dynamic tools"""
        return list(self._dynamic_tools.keys())
        
    def list_mcp_servers(self) -> List[str]:
        """List all MCP servers"""
        return list(self._mcp_servers.keys())
        
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up dynamic tools and servers")
        
        # Clean up tools
        for tool in self._dynamic_tools.values():
            if hasattr(tool, 'cleanup'):
                await tool.cleanup()
                
        # Clean up servers
        for server in self._mcp_servers.values():
            if hasattr(server["implementation"], 'cleanup'):
                await server["implementation"].cleanup()
                
        self._dynamic_tools.clear()
        self._mcp_servers.clear()
