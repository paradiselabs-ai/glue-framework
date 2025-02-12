"""Test dynamic tool and MCP server creation through natural language"""

import pytest
import pytest_asyncio
import os
from pathlib import Path

from glue.core.app import GlueApp
from glue.dsl.parser import parse_glue_file
from glue.dsl.executor import execute_glue_app
from glue.core.types import AdhesiveType

@pytest_asyncio.fixture
async def app():
    """Get running research assistant app instance"""
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    yield app
    await app.cleanup()

@pytest.mark.asyncio
async def test_custom_tool_creation():
    """Test creating a custom tool through natural language"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Request to create a custom citation formatting tool
        result = await app.process_prompt(
            "Create a tool that can format text in APA citation style"
        )
        
        # Verify tool was created
        assert "created" in result.lower()
        assert "citation" in result.lower()
        
        # Test using the new tool
        test_result = await app.process_prompt(
            'Format this as a citation: "The Impact of Quantum Computing" by John Smith, published in 2024'
        )
        
        # Verify citation formatting
        assert "Smith, J." in test_result
        assert "2024" in test_result
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_mcp_server_creation():
    """Test creating an MCP server through natural language"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Request to create a weather MCP server
        result = await app.process_prompt(
            "Create an MCP server that can provide weather forecasts for any city"
        )
        
        # Verify server was created
        assert "created" in result.lower()
        assert "weather" in result.lower()
        
        # Test using the new MCP server
        test_result = await app.process_prompt(
            "What's the weather forecast for London?"
        )
        
        # Verify weather information
        assert "temperature" in test_result.lower() or "forecast" in test_result.lower()
        assert "london" in test_result.lower()
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_tool_chain_creation():
    """Test creating a chain of tools through natural language"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Request to create a research pipeline
        result = await app.process_prompt(
            """Create a tool chain that can:
            1. Search for academic papers
            2. Extract key findings
            3. Format citations
            4. Generate a summary report"""
        )
        
        # Verify tool chain was created
        assert "created" in result.lower()
        assert "chain" in result.lower() or "pipeline" in result.lower()
        
        # Test using the tool chain
        test_result = await app.process_prompt(
            "Research recent papers about quantum computing and create a summary with citations"
        )
        
        # Verify chain output
        assert "findings" in test_result.lower()
        assert "references" in test_result.lower() or "citations" in test_result.lower()
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_tool_modification():
    """Test modifying existing tools through natural language"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Request to enhance the web search tool
        result = await app.process_prompt(
            "Enhance the web search tool to also extract and summarize key points from each result"
        )
        
        # Verify tool was modified
        assert "enhanced" in result.lower() or "modified" in result.lower()
        assert "search" in result.lower()
        
        # Test using the enhanced tool
        test_result = await app.process_prompt(
            "Search for quantum computing breakthroughs"
        )
        
        # Verify enhanced output
        assert "key points" in test_result.lower() or "summary" in test_result.lower()
        assert "quantum" in test_result.lower()
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_collaborative_tool_creation():
    """Test models collaborating to create tools"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Request collaborative tool creation
        result = await app.process_prompt(
            """Have the researcher and assistant collaborate to create:
            1. A tool to analyze research trends
            2. A tool to generate visualizations
            3. A tool to create interactive reports"""
        )
        
        # Verify tools were created collaboratively
        assert "created" in result.lower()
        assert "tools" in result.lower()
        
        # Test using the collaborative tools
        test_result = await app.process_prompt(
            "Analyze trends in quantum computing research and create an interactive report with visualizations"
        )
        
        # Verify collaborative output
        assert "trends" in test_result.lower()
        assert "visualization" in test_result.lower() or "graph" in test_result.lower()
        assert "interactive" in test_result.lower() or "report" in test_result.lower()
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_natural_tool_requests():
    """Test natural language tool requests in research context"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Make natural tool requests during research
        result = await app.process_prompt(
            """Research quantum computing advancements. While doing this:
            - Create any tools you need for better analysis
            - Set up any helpful MCP servers
            - Enhance existing tools as needed"""
        )
        
        # Verify dynamic tool creation and usage
        assert "quantum" in result.lower()
        assert "computing" in result.lower()
        assert "created" in result.lower() or "enhanced" in result.lower()
        
        # Verify tools were actually created/enhanced
        tools_result = await app.process_prompt(
            "List all available tools and their capabilities"
        )
        
        # Check for new/enhanced tools
        assert "analysis" in tools_result.lower()
        assert "created" in tools_result.lower() or "enhanced" in tools_result.lower()
        
    finally:
        await app.cleanup()
