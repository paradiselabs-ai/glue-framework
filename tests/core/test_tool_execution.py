"""Test SmolAgents tool execution integration"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from glue.core.types import AdhesiveType, ToolResult
from glue.tools.executor import SmolAgentsToolExecutor, ToolIntent
from glue.core.model import Model
from datetime import datetime

@pytest.fixture
def mock_team():
    team = MagicMock()
    team.tools = {
        "web_search": MagicMock(),
        "file_handler": MagicMock()
    }
    team.share_result = AsyncMock()
    return team

@pytest.fixture
def mock_model(mock_team):
    model = MagicMock(spec=Model)
    model.name = "test_model"
    model.team = mock_team
    model.available_adhesives = {AdhesiveType.GLUE, AdhesiveType.VELCRO, AdhesiveType.TAPE}
    model._tools = mock_team.tools
    model.generate = AsyncMock()
    return model

@pytest.fixture
def executor(mock_team):
    return SmolAgentsToolExecutor(
        team=mock_team,
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO, AdhesiveType.TAPE}
    )

@pytest.mark.asyncio
async def test_natural_language_tool_execution(mock_model, executor):
    """Test executing tools from natural language"""
    # Mock model response with natural language tool intent
    mock_model.generate.return_value = """
    I'll search the web for information about Python programming.
    Let me use the web search tool to find some resources.
    """
    
    # Mock SmolAgent parsing
    with patch("smolagents.SmolAgent") as MockSmolAgent:
        mock_agent = MockSmolAgent.return_value
        mock_agent.parse_intent.return_value = {
            "tool": "web_search",
            "input": "Python programming tutorials",
            "adhesive": "GLUE",
            "description": "Search for Python programming resources"
        }
        
        # Mock tool execution
        mock_model.team.tools["web_search"].execute = AsyncMock(
            return_value="Found Python tutorials at python.org"
        )
        
        # Process the prompt
        result = await mock_model.process("Tell me about Python programming")
        
        # Verify natural language was parsed correctly
        mock_agent.parse_intent.assert_called_once()
        assert "python.org" in result

@pytest.mark.asyncio
async def test_dynamic_tool_creation(executor):
    """Test creating tools dynamically"""
    # Mock tool intent for new tool
    intent = ToolIntent(
        tool_name="custom_tool",
        input_data={"param": "value"},
        adhesive=AdhesiveType.GLUE,
        description="A custom tool for testing"
    )
    
    # Mock SmolAgents tool creation
    with patch("smolagents.create_tool") as mock_create_tool:
        mock_tool = AsyncMock()
        mock_tool.execute = AsyncMock(return_value="Custom tool result")
        mock_create_tool.return_value = mock_tool
        
        # Create and execute tool
        tool = await executor._create_dynamic_tool(
            name=intent.tool_name,
            description=intent.description
        )
        
        # Verify tool was created
        assert tool == mock_tool
        assert intent.tool_name in executor._dynamic_tools

@pytest.mark.asyncio
async def test_mcp_tool_creation(executor):
    """Test creating tools from MCP servers"""
    with patch.object(executor, "_get_mcp_schema") as mock_get_schema:
        # Mock MCP schema
        mock_get_schema.return_value = {
            "description": "Weather forecast tool",
            "parameters": {
                "city": "string",
                "days": "integer"
            }
        }
        
        # Mock SmolAgents tool creation
        with patch("smolagents.create_tool") as mock_create_tool:
            mock_tool = AsyncMock()
            mock_create_tool.return_value = mock_tool
            
            # Create MCP tool
            tool = await executor.create_mcp_tool(
                server_name="weather",
                tool_name="get_forecast"
            )
            
            # Verify tool was created with MCP schema
            assert tool == mock_tool
            assert "weather_get_forecast" in executor._dynamic_tools

@pytest.mark.asyncio
async def test_adhesive_handling(mock_model, executor):
    """Test handling different adhesive types"""
    # Test GLUE adhesive
    glue_result = ToolResult(
        tool_name="web_search",
        result="Shared result",
        adhesive=AdhesiveType.GLUE,
        timestamp=datetime.now()
    )
    
    await mock_model.team.share_result(glue_result)
    mock_model.team.share_result.assert_called_once_with(glue_result)
    
    # Test VELCRO adhesive
    mock_model._session_results = {}
    velcro_result = ToolResult(
        tool_name="file_handler",
        result="Session result",
        adhesive=AdhesiveType.VELCRO,
        timestamp=datetime.now()
    )
    
    mock_model._session_results[velcro_result.tool_name] = velcro_result
    assert mock_model._session_results["file_handler"] == velcro_result
