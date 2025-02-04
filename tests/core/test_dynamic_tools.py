"""Test dynamic tool creation and team interactions with SmolAgents"""

import pytest
from glue.providers.smolagents import SmolAgentsProvider
from glue.core.types import AdhesiveType
from glue.core.team import Team

@pytest.mark.asyncio
async def test_dynamic_tool_creation():
    """Test creating a tool dynamically"""
    # Create team
    team = Team(name="research_team")
    
    # Create provider
    provider = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO, AdhesiveType.TAPE},
        api_key="test-key"
    )
    
    # Define tool function
    async def format_citation(text: str) -> str:
        return f"Citation: {text}\nFormatted according to APA style"
    
    # Create tool dynamically
    tool = await provider.create_tool(
        name="citation_formatter",
        description="Format text in APA citation style",
        function=format_citation
    )
    
    # Verify tool was created
    assert tool.name == "citation_formatter"
    assert "APA" in tool.description
    
    # Test using tool with GLUE adhesive
    result = await provider.use_tool(
        tool_name="citation_formatter",
        adhesive=AdhesiveType.GLUE,
        input_data="Smith, J. (2024). AI Development."
    )
    
    assert "Citation:" in result.result
    assert "APA style" in result.result
    
    # Verify result was shared with team
    assert "citation_formatter" in team.shared_results

@pytest.mark.asyncio
async def test_mcp_tool_creation():
    """Test creating a tool from MCP server"""
    # Create team
    team = Team(name="weather_team")
    
    # Create provider
    provider = SmolAgentsProvider(
        name="forecaster",
        team="weather_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        api_key="test-key"
    )
    
    # Create MCP tool
    tool = await provider.create_mcp_tool(
        server_name="weather-server",
        tool_name="get_forecast"
    )
    
    # Verify tool was created
    assert tool.name == "weather-server_get_forecast"
    assert tool in team.tools.values()
    
    # Test using tool with VELCRO adhesive
    result = await provider.use_tool(
        tool_name="weather-server_get_forecast",
        adhesive=AdhesiveType.VELCRO,
        input_data={"city": "London"}
    )
    
    assert isinstance(result.result, str)
    assert result.adhesive == AdhesiveType.VELCRO
    
    # Verify result was kept in session
    assert "weather-server_get_forecast" in provider._session_results

@pytest.mark.asyncio
async def test_team_communication():
    """Test team communication with dynamic tools"""
    # Create teams
    research_team = Team(name="research_team")
    analysis_team = Team(name="analysis_team")
    
    # Create providers
    researcher = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    analyst = SmolAgentsProvider(
        name="analyst",
        team="analysis_team", 
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    # Create dynamic tools
    async def collect_data(topic: str) -> str:
        return f"Data collected about {topic}"
        
    async def analyze_data(data: str) -> str:
        return f"Analysis of: {data}\nFindings: Important insights"
    
    research_tool = await researcher.create_tool(
        name="data_collector",
        description="Collect research data",
        function=collect_data
    )
    
    analysis_tool = await analyst.create_tool(
        name="data_analyzer",
        description="Analyze research data",
        function=analyze_data
    )
    
    # Test team collaboration
    # 1. Researcher collects data
    collect_result = await researcher.use_tool(
        tool_name="data_collector",
        adhesive=AdhesiveType.GLUE,
        input_data="AI trends"
    )
    
    assert "Data collected" in collect_result.result
    assert "data_collector" in research_team.shared_results
    
    # 2. Analyst analyzes data
    analysis_result = await analyst.use_tool(
        tool_name="data_analyzer",
        adhesive=AdhesiveType.GLUE,
        input_data=collect_result.result
    )
    
    assert "Analysis of:" in analysis_result.result
    assert "data_analyzer" in analysis_team.shared_results
    
    # Verify team results are separate
    assert "data_collector" not in analysis_team.shared_results
    assert "data_analyzer" not in research_team.shared_results
