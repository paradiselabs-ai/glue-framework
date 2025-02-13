"""Dynamic Tool Factory for GLUE Framework

This module provides sophisticated tool creation capabilities that integrate
with SmolAgents while maintaining GLUE's team and adhesive mechanics.
"""

import asyncio
from typing import Dict, Any, Optional, List, Union, Callable, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

from ..core.types import AdhesiveType
from .base import BaseTool
from ..core.model import Model
from ..core.logger import get_logger

if TYPE_CHECKING:
    from ..core.team import Team

from pydantic import BaseModel, Field, validator
from prefect import task, flow
from typing import List, Dict, Any, Optional

class ToolInput(BaseModel):
    """Pydantic model for tool input validation"""
    type: str = Field(..., description="Input type (string, number, boolean, etc)")
    description: str = Field(..., description="Input description")
    optional: bool = Field(default=False, description="Whether input is optional")
    default: Optional[Any] = Field(default=None, description="Default value if optional")
    
    @validator('type')
    def validate_type(cls, v):
        valid_types = {'string', 'number', 'boolean', 'object', 'array'}
        if v not in valid_types:
            raise ValueError(f"Invalid type: {v}. Must be one of {valid_types}")
        return v

class ToolSpec(BaseModel):
    """Pydantic model for tool specification"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputs: Dict[str, ToolInput] = Field(..., description="Tool inputs")
    output_type: str = Field(default="string", description="Output type")
    adhesive_types: Optional[List[AdhesiveType]] = Field(default=None, description="Allowed adhesive types")
    team_name: Optional[str] = Field(default=None, description="Team name")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError(f"Invalid tool name: {v}. Must be a valid Python identifier")
        return v

class MCPServerSpec(BaseModel):
    """Pydantic model for MCP server specification"""
    name: str = Field(..., description="Server name")
    tools: List[ToolSpec] = Field(..., description="Server tools")
    env_vars: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")
    base_url: Optional[str] = Field(default=None, description="Base URL")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.isidentifier():
            raise ValueError(f"Invalid server name: {v}. Must be a valid Python identifier")
        return v

class DynamicToolFactory:
    """Factory for creating tools and MCP servers dynamically"""
    
    _instance = None
    _tool_classes = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def get_tool_class(cls, tool_name: str) -> Optional[BaseTool]:
        """Get tool class by name (static method for orchestrator compatibility)"""
        instance = cls.get_instance()
        return instance.get_tool(tool_name)
    
    def __init__(self):
        self.logger = get_logger()
        self._dynamic_tools: Dict[str, BaseTool] = {}
        self._mcp_servers: Dict[str, Any] = {}
        
    @task(name="validate_tool_spec")
    async def validate_tool_spec(self, spec: ToolSpec) -> None:
        """Validate tool specification using Pydantic"""
        try:
            # This will raise validation errors if spec is invalid
            ToolSpec.validate(spec)
            self.logger.info(f"Tool spec validation successful: {spec.name}")
        except Exception as e:
            self.logger.error(f"Tool spec validation failed: {str(e)}")
            raise

    @task(name="create_smol_tool")
    async def create_smol_tool(self, spec: ToolSpec) -> Callable:
        """Create SmolAgents tool implementation"""
        from smolagents import SmolAgent, tool
        
        agent = SmolAgent()
        tool_impl = await agent.create_tool_implementation(
            name=spec.name,
            description=spec.description,
            inputs={name: input_spec.dict() for name, input_spec in spec.inputs.items()},
            output_type=spec.output_type
        )
        
        @tool
        async def dynamic_tool(input: str) -> str:
            """Execute the SmolAgents tool implementation"""
            return await tool_impl(input)
            
        return dynamic_tool

    @flow(name="create_tool")
    async def create_tool_from_spec(
        self,
        spec: ToolSpec,
        team: Optional['Team'] = None
    ) -> BaseTool:
        """Create a tool from specification with Prefect orchestration"""
        self.logger.info(f"Creating tool: {spec.name}")
        
        try:
            # Validate spec
            await self.validate_tool_spec(spec)
            
            # Create SmolAgents tool
            dynamic_tool = await self.create_smol_tool(spec)
            
            # Wrap in GLUE BaseTool
            tool_instance = BaseTool(
                name=spec.name,
                description=spec.description,
                execute=dynamic_tool,
                inputs=spec.inputs,
                output_type=spec.output_type
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
            
    @task(name="validate_mcp_spec")
    async def validate_mcp_spec(self, spec: MCPServerSpec) -> None:
        """Validate MCP server specification"""
        try:
            MCPServerSpec.validate(spec)
            self.logger.info(f"MCP server spec validation successful: {spec.name}")
        except Exception as e:
            self.logger.error(f"MCP server spec validation failed: {str(e)}")
            raise

    @flow(name="create_mcp_server")
    async def create_mcp_server_from_spec(
        self,
        spec: MCPServerSpec,
        team: Optional['Team'] = None
    ) -> Dict[str, BaseTool]:
        """Create MCP server and its tools with Prefect orchestration"""
        self.logger.info(f"Creating MCP server: {spec.name}")
        
        try:
            # Validate server spec
            await self.validate_mcp_spec(spec)
            
            # Create tools for each server endpoint
            tools = {}
            for tool_spec in spec.tools:
                # Each tool creation is a subflow
                tool = await self.create_tool_from_spec(tool_spec, team)
                tools[tool_spec.name] = tool
                
            # Store server
            self._mcp_servers[spec.name] = {
                "tools": tools,
                "spec": spec
            }
            
            self.logger.info(f"Successfully created MCP server: {spec.name}")
            return tools
            
        except Exception as e:
            self.logger.error(f"Failed to create MCP server {spec.name}: {str(e)}")
            raise
            
    @task(name="parse_tool_intent")
    async def parse_tool_intent(self, request: str) -> Optional[Dict[str, Any]]:
        """Parse tool creation intent using SmolAgents"""
        from smolagents import SmolAgent
        
        agent = SmolAgent()
        intent = await agent.parse_tool_intent(request)
        
        if intent:
            self.logger.info(f"Parsed tool intent: {intent['type']}")
        else:
            self.logger.warning("No tool intent found in request")
            
        return intent

    @flow(name="parse_natural_request")
    async def parse_natural_request(
        self,
        request: str,
        team: Optional['Team'] = None
    ) -> Union[BaseTool, Dict[str, BaseTool], None]:
        """Parse and handle natural language tool creation request with Prefect orchestration"""
        self.logger.info("Parsing tool creation request")
        
        try:
            # Parse intent as a task
            intent = await self.parse_tool_intent(request)
            
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
            
    @task(name="generate_enhanced_implementation")
    async def generate_enhanced_implementation(
        self,
        tool: BaseTool,
        enhancement_request: str
    ) -> Callable:
        """Generate enhanced tool implementation using SmolAgents"""
        from smolagents import SmolAgent
        
        agent = SmolAgent()
        return await agent.enhance_tool_implementation(
            name=tool.name,
            description=tool.description,
            current_implementation=tool.execute,
            enhancement_request=enhancement_request
        )

    @flow(name="enhance_tool")
    async def enhance_tool(
        self,
        tool_name: str,
        enhancement_request: str,
        team: Optional['Team'] = None
    ) -> BaseTool:
        """Enhance existing tool with Prefect orchestration"""
        self.logger.info(f"Enhancing tool: {tool_name}")
        
        try:
            # Get existing tool
            tool = self._dynamic_tools.get(tool_name)
            if not tool:
                raise ValueError(f"Tool {tool_name} not found")
                
            # Generate enhanced implementation as a task
            enhanced_impl = await self.generate_enhanced_implementation(tool, enhancement_request)
            
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
