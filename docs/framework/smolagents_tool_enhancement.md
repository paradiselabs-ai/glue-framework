# SmolAgents Tool Enhancement Plan

## Overview

Use SmolAgents to enhance GLUE's tool system while preserving GLUE's core team and adhesive mechanics:
- Teams own tools (not individual agents)
- Agents use team tools with their allowed adhesives
- Free team communication
- Magnetic field for team interactions

## Tool Implementation Details

### Core Tool Structure
```python
from smolagents import Tool

class CustomTool(Tool):
    def __init__(self):
        # Required SmolAgents attributes
        self.name = "tool_name"
        self.description = "Tool description for the LLM"
        self.inputs = {
            "param1": {
                "type": "string",
                "description": "Description of parameter 1",
                "optional": False
            },
            "param2": {
                "type": "number",
                "description": "Description of parameter 2",
                "optional": True
            }
        }
        self.output_type = "string"  # All tools must return strings
        
    async def forward(self, *args, **kwargs) -> str:
        """Main execution method required by SmolAgents"""
        # Process inputs and execute tool logic
        result = await self._process_inputs(*args, **kwargs)
        # Must return string
        return str(result)
```

### Key Requirements
1. Must inherit from smolagents.Tool
2. Must define name, description, inputs (with types and descriptions), and output_type
3. Must implement forward method that returns a string
4. Input validation is handled by SmolAgents based on input definitions
5. Tool results must be converted to strings before returning

## Tool System Enhancements

### 1. Dynamic Tool Creation
```python
class SmoLAgentsProvider(BaseProvider):
    async def create_tool(self, name: str, description: str, function: Any) -> AdhesiveTool:
        """Create a new tool on the fly"""
        # Convert to SmolAgents tool
        @tool
        async def dynamic_tool(*args, **kwargs):
            return await function(*args, **kwargs)
            
        # Add to team's available tools
        tool = AdhesiveTool(
            name=name,
            description=description,
            execute=dynamic_tool
        )
        await self.team.add_tool(name, tool)
        return tool
```

### 2. MCP Integration
```python
class SmoLAgentsProvider(BaseProvider):
    async def create_mcp_tool(self, server_name: str, tool_name: str) -> AdhesiveTool:
        """Create tool from MCP server"""
        # Get tool schema from MCP
        schema = await get_mcp_tool_schema(server_name, tool_name)
        
        # Create SmolAgents tool that uses MCP
        @tool
        async def mcp_tool(*args, **kwargs):
            return await use_mcp_tool(
                server_name=server_name,
                tool_name=tool_name,
                arguments=kwargs
            )
            
        # Add to team's tools
        tool = AdhesiveTool(
            name=f"{server_name}_{tool_name}",
            description=schema.description,
            execute=mcp_tool
        )
        await self.team.add_tool(tool.name, tool)
        return tool
```

### 3. Enhanced Tool Execution
```python
class SmoLAgentsProvider(BaseProvider):
    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use tool with enhanced execution"""
        # Validate adhesive and tool
        if adhesive not in self.available_adhesives:
            raise ValueError(f"Model {self.name} cannot use {adhesive.name} adhesive")
            
        # Get tool from team
        tool = await self.team.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not available to team {self.team.name}")
            
        # Import team data if using GLUE
        if adhesive == AdhesiveType.GLUE:
            await tool.import_team_data(self.team.shared_results.get(tool_name))
            
        # Execute through SmolAgents for enhanced capabilities
        agent = self._get_agent(tool_name)
        smol_tool = self._convert_tool(tool)
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
            await self.team.share_result(tool_name, tool_result)
        elif adhesive == AdhesiveType.VELCRO:
            self._session_results[tool_name] = tool_result
            
        return tool_result
```

## Benefits of SmolAgents Integration

### 1. Natural Language Tool Usage
- Models can use tools without XML tags
- More natural interaction flow
- Better error messages

### 2. Input Validation
- Automatic type checking
- Required vs optional parameters
- Input descriptions for models

### 3. Standardized Interface
- Consistent tool structure
- String-based outputs
- Clear input specifications

### Original Benefits

1. Dynamic Tool Creation
- Create tools on demand
- Adapt to changing needs
- Easy function wrapping

2. MCP Integration
- Seamless MCP tool access
- Automatic schema handling
- Tool sharing between teams

3. Enhanced Execution
- Better error handling
- Improved documentation
- Proper adhesive handling

## Implementation Steps

1. Update SmoLAgentsProvider
- [ ] Remove agent management focus
- [ ] Add dynamic tool creation
- [ ] Add MCP integration
- [ ] Enhance tool execution

2. Update Tool System
- [ ] Support dynamic creation
- [ ] Handle MCP tools
- [ ] Improve documentation

3. Testing
- [ ] Dynamic tool creation
- [ ] MCP integration
- [ ] Adhesive compliance
- [ ] Team tool sharing

## Example Usage

```python
# Dynamic tool creation
async def search_news(query: str) -> str:
    # Custom news search implementation
    pass
    
news_tool = await model.create_tool(
    name="news_search",
    description="Search recent news articles",
    function=search_news
)

# MCP tool creation
mcp_tool = await model.create_mcp_tool(
    server_name="weather-server",
    tool_name="get_forecast"
)

# Using tools with adhesives
# GLUE - share with team
await model.use_tool("news_search", AdhesiveType.GLUE, "AI developments")

# VELCRO - keep for session
await model.use_tool("get_forecast", AdhesiveType.VELCRO, {"city": "London"})

# TAPE - one-time use
await model.use_tool("news_search", AdhesiveType.TAPE, "quick fact check")
