"""Dynamic Tool Factory for GLUE Framework

This module provides sophisticated tool creation capabilities that integrate
with SmolAgents while maintaining GLUE's team and adhesive mechanics.
"""

import asyncio
from smolagents.tools import Tool, AUTHORIZED_TYPES
from smolagents.agents import ToolCallingAgent
from typing import Dict, Any, Optional, List, Union, Callable, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

from ..core.types import AdhesiveType
from .base import BaseTool
from ..core.model import Model
from ..core.logger import get_logger

if TYPE_CHECKING:
    from ..core.team import Team
    from ..core.workspace import Workspace
    from ..magnetic.field import MagneticField

from pydantic import BaseModel, Field, field_validator
from prefect import task, flow
from typing import List, Dict, Any, Optional


class ToolInput(BaseModel):
    """Pydantic model for tool input validation"""

    type: str = Field(..., description="Input type (string, number, boolean, etc)")
    description: str = Field(..., description="Input description")
    optional: bool = Field(default=False, description="Whether input is optional")
    default: Optional[Any] = Field(default=None, description="Default value if optional")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        from smolagents import AUTHORIZED_TYPES
        if v not in AUTHORIZED_TYPES:
            raise ValueError(f"Invalid type: {v}. Must be one of {AUTHORIZED_TYPES}")
        return v


class ToolSpec(BaseModel):
    """Pydantic model for tool specification"""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputs: Dict[str, ToolInput] = Field(..., description="Tool inputs")
    output_type: str = Field(default="string", description="Output type")
    adhesive_types: Optional[List[AdhesiveType]] = Field(
        default=None, description="Allowed adhesive types"
    )
    team_name: Optional[str] = Field(default=None, description="Team name")
    function: Optional[Callable] = Field(default=None, description="Tool implementation function")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"Invalid tool name: {v}. Must be a valid Python identifier")
        return v


class MCPServerSpec(BaseModel):
    """Pydantic model for MCP server specification"""

    name: str = Field(..., description="Server name")
    tools: List[ToolSpec] = Field(..., description="Server tools")
    env_vars: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")
    base_url: Optional[str] = Field(default=None, description="Base URL")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
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
        self.logger = get_logger("DynamicToolFactory")
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
    async def create_smol_tool(self, spec: ToolSpec, function: Optional[Callable] = None) -> Callable:
        """Create SmolAgents tool implementation"""
        from smolagents.tools import Tool
        from smolagents.agent import ToolCallingAgent
        from smolagents.model import Model
        
        class DynamicTool(Tool):
            name = spec.name
            description = spec.description
            inputs = spec.inputs or {
                "text": {
                    "type": "string",
                    "description": "Input text to format"
                }
            }
            output_type = "string"
            
            async def forward(self, *args, **kwargs) -> str:
                """Execute the tool implementation"""
                if function:
                    # Get the first parameter name from the function signature
                    import inspect
                    sig = inspect.signature(function)
                    param_name = next(iter(sig.parameters))
                    
                    # Extract value from kwargs based on parameter name
                    if param_name in kwargs:
                        return await function(**{param_name: kwargs[param_name]})
                    elif args:
                        return await function(**{param_name: args[0]})
                    else:
                        raise ValueError(f"Missing required parameter: {param_name}")
                return kwargs.get('input', '')
        
        tool = DynamicTool()
        agent = ToolCallingAgent(tools=[tool], model=Model())
        return tool.forward

    @flow(name="create_tool_flow")
    async def create_tool_flow(
        self, name: str, description: str, function: Callable, team: Optional[Any] = None
    ) -> BaseTool:
        """Create a tool from specification with Prefect orchestration"""
        # Extract first parameter name from function
        import inspect
        sig = inspect.signature(function)
        param_name = next(iter(sig.parameters))
        
        spec = ToolSpec(
            name=name,
            description=description,
            inputs={
                param_name: ToolInput(
                    type="string",
                    description=f"Input for {param_name}"
                )
            },
            output_type="string",
            function=function
        )
        return await self.create_tool_from_spec(spec, team)

    @flow(name="create_tool")
    async def create_tool_from_spec(
        self, spec: ToolSpec, team: Optional[Any] = None
    ) -> BaseTool:
        """Create a tool from specification with Prefect orchestration"""
        self.logger.info(f"Creating tool: {spec.name}")

        try:
            # Validate spec
            await self.validate_tool_spec(spec)

            # Create SmolAgents tool with function if provided
            dynamic_tool = await self.create_smol_tool(spec, function=getattr(spec, 'function', None))

            # Create tool class
            class CustomTool(BaseTool):
                name = spec.name
                description = spec.description
                inputs = spec.inputs
                output_type = spec.output_type
                tool_name = spec.name
                tool_description = spec.description
                
                async def execute(self, input_data: Any) -> Any:
                    # Convert input_data to kwargs based on first input key
                    input_key = next(iter(spec.inputs))
                    kwargs = {input_key: input_data}
                    return await dynamic_tool(**kwargs)
                
                async def forward(self, **kwargs) -> str:
                    # Forward to execute with proper input handling
                    input_key = next(iter(spec.inputs))
                    if input_key in kwargs:
                        return await self.execute(kwargs[input_key])
                    return await self.execute(kwargs)
            
            # Create instance with required config
            tool_instance = CustomTool(
                config={
                    "required_permissions": [],  # Default to no special permissions required
                    "tool_specific_config": spec.model_dump()
                }
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
        self, spec: MCPServerSpec, team: Optional[Any] = None
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
            self._mcp_servers[spec.name] = {"tools": tools, "spec": spec}

            self.logger.info(f"Successfully created MCP server: {spec.name}")
            return tools

        except Exception as e:
            self.logger.error(f"Failed to create MCP server {spec.name}: {str(e)}")
            raise

    @task(name="parse_tool_intent")
    async def parse_tool_intent(self, request: str) -> Optional[Dict[str, Any]]:
        """Parse tool creation intent using SmolAgents"""
        agent = ToolCallingAgent()
        intent = await agent.parse_message(request)

        if intent:
            self.logger.info(f"Parsed tool intent: {intent['type']}")
        else:
            self.logger.warning("No tool intent found in request")

        return intent

    @flow(name="parse_natural_request")
    async def parse_natural_request(
        self, request: str, team: Optional[Any] = None
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
                    output_type=intent.get("output_type", "string"),
                )
                return await self.create_tool_from_spec(spec, team)

            elif intent.get("type") == "mcp":
                # Create MCP server with tools
                spec = MCPServerSpec(
                    name=intent["server_name"],
                    tools=[
                        ToolSpec(
                            name=intent["tool_name"],
                            description=intent["description"],
                            inputs=intent.get("inputs", {}),
                            output_type=intent.get("output_type", "string"),
                        )
                    ],
                )
                return await self.create_mcp_server_from_spec(spec, team)

            return None

        except Exception as e:
            self.logger.error(f"Failed to parse tool request: {str(e)}")
            raise

    @task(name="generate_enhanced_implementation")
    async def generate_enhanced_implementation(
        self, tool: BaseTool, enhancement_request: str
    ) -> Callable:
        """Generate enhanced tool implementation using SmolAgents"""
        from smolagents.agent import ToolCallingAgent

        agent = ToolCallingAgent()
        return await agent.enhance_tool_implementation(
            name=tool.name,
            description=tool.description,
            current_implementation=tool.execute,
            enhancement_request=enhancement_request,
        )

    @flow(name="enhance_tool")
    async def enhance_tool(
        self, tool_name: str, enhancement_request: str, team: Optional[Any] = None
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
                    output_type=tool.output_type,
                ),
                team,
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

    @task(name="execute_tool_parallel")
    async def execute_tool_parallel(self, tool: BaseTool, input_data: Any) -> Any:
        """Execute a single tool in parallel task"""
        return await tool.execute(input_data)

    @flow(name="execute_tools_parallel")
    async def execute_tools_parallel(self, tools: List[BaseTool], inputs: List[Any]) -> List[Any]:
        """Execute multiple tools in parallel"""
        if len(tools) != len(inputs):
            raise ValueError("Number of tools must match number of inputs")

        # Create parallel tasks for each tool execution
        tasks = [
            self.execute_tool_parallel(tool, input_data) for tool, input_data in zip(tools, inputs)
        ]

        # Execute all tasks in parallel
        return await asyncio.gather(*tasks)

    @task(name="create_single_tool_parallel")
    async def create_single_tool_parallel(
        self, tool_spec: Dict[str, Any], team: Optional[Any] = None
    ) -> BaseTool:
        """Create a single tool as a parallel task"""
        # Extract first parameter name from function if provided
        param_name = tool_spec.get("name", "input").split("_")[0]
        
        spec = ToolSpec(
            name=tool_spec["name"],
            description=tool_spec["description"],
            inputs={
                param_name: ToolInput(
                    type="string",
                    description=f"Input for {param_name}"
                )
            },
            output_type="string",
            function=tool_spec.get("function")  # Pass function if provided
        )
        return await self.create_tool_from_spec(spec, team)

    @flow(name="create_tools_parallel")
    async def create_tools_parallel(
        self, tool_specs: List[Dict[str, Any]], team: Optional[Any] = None
    ) -> List[BaseTool]:
        """Create multiple tools in parallel"""
        # Create parallel tasks for each tool creation
        tasks = [self.create_single_tool_parallel(spec, team) for spec in tool_specs]

        # Execute all tasks in parallel
        return await asyncio.gather(*tasks)

    @flow(name="create_tool_with_retries")
    async def create_tool_with_retries(
        self,
        name: str,
        description: str,
        function: Callable,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        team: Optional[Any] = None,
    ) -> BaseTool:
        """Create a tool with retry policy"""

        @task(
            name=f"{name}_with_retries",
            retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        async def retrying_function(*args, **kwargs):
            return await function(*args, **kwargs)

        # Extract first parameter name from function
        import inspect
        sig = inspect.signature(function)
        param_name = next(iter(sig.parameters))
        
        spec = ToolSpec(
            name=name,
            description=description,
            inputs={
                param_name: ToolInput(
                    type="string",
                    description=f"Input for {param_name}"
                )
            },
            output_type="string",
            function=function  # Store function in spec
        )

        tool = await self.create_tool_from_spec(spec, team)
        tool.execute = retrying_function
        return tool

    @flow(name="create_tool_with_state")
    async def create_tool_with_state(
        self,
        name: str,
        description: str,
        function: Callable,
        initial_state: Dict[str, Any],
        team: Optional[Any] = None,
    ) -> BaseTool:
        """Create a tool that maintains state"""
        # Extract first parameter name from function
        import inspect
        sig = inspect.signature(function)
        param_name = next(iter(sig.parameters))
        
        spec = ToolSpec(
            name=name,
            description=description,
            inputs={
                param_name: ToolInput(
                    type="string",
                    description=f"Input for {param_name}"
                )
            },
            output_type="string",
            function=function  # Store function in spec
        )

        tool = await self.create_tool_from_spec(spec, team)
        tool.state = initial_state
        tool.execute = function
        return tool

    @flow(name="create_tool_chain")
    async def create_tool_chain(
        self, tools: List[Dict[str, Any]], team: Optional[Any] = None
    ) -> BaseTool:
        """Create a chain of tools that execute sequentially"""
        # Create all tools first
        created_tools = await self.create_tools_parallel(tools, team)

        # Create chain function that executes tools in sequence
        async def chain_execute(input_data: Any) -> Any:
            result = input_data
            for tool in created_tools:
                result = await tool.execute(result)
            return result

        # Create chain tool
        # Extract first parameter name from first tool's function
        import inspect
        first_tool = created_tools[0]
        if hasattr(first_tool, 'function') and first_tool.function:
            sig = inspect.signature(first_tool.function)
            param_name = next(iter(sig.parameters))
        else:
            param_name = "input"
            
        chain_spec = ToolSpec(
            name=f"chain_{created_tools[0].name}",
            description=f"Chain of tools: {', '.join(t.name for t in created_tools)}",
            inputs={
                param_name: ToolInput(
                    type="string",
                    description=f"Input for chain of tools"
                )
            },
            output_type="string"
        )

        chain_tool = await self.create_tool_from_spec(chain_spec, team)
        chain_tool.execute = chain_execute
        chain_tool.chain_tools = created_tools
        return chain_tool

    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up dynamic tools and servers")

        # Clean up tools
        for tool in self._dynamic_tools.values():
            if hasattr(tool, "cleanup"):
                await tool.cleanup()

        # Clean up servers
        for server in self._mcp_servers.values():
            if hasattr(server["implementation"], "cleanup"):
                await server["implementation"].cleanup()

        self._dynamic_tools.clear()
        self._mcp_servers.clear()
