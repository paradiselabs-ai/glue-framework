"""Test SmolAgents tool integration"""

import pytest
from smolagents import Tool
from glue.tools.file_handler import FileHandlerTool
from glue.tools.web_search import WebSearchTool
from glue.tools.code_interpreter import CodeInterpreterTool
from glue.tools.mock_tools import (
    MockWebSearchTool,
    MockFileHandlerTool,
    MockAPAFormatterTool,
    MockWeatherTool
)

@pytest.mark.asyncio
async def test_file_handler_tool():
    """Test file handler with SmolAgents integration"""
    tool = FileHandlerTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert tool.name == "file_handler"
    assert tool.description
    assert tool.inputs
    assert tool.output_type == "string"
    
    # Test write operation
    result = await tool.forward(
        action="write",
        path="test.txt",
        content="Hello, World!"
    )
    assert isinstance(result, str)
    assert "success" in result.lower()
    
    # Test read operation
    result = await tool.forward(
        action="read",
        path="test.txt"
    )
    assert isinstance(result, str)
    assert "Hello, World!" in result

@pytest.mark.asyncio
async def test_web_search_tool():
    """Test web search with SmolAgents integration"""
    tool = WebSearchTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert tool.name == "web_search"
    assert tool.description
    assert tool.inputs
    assert tool.output_type == "string"
    
    # Test search
    result = await tool.forward(query="quantum computing")
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_code_interpreter_tool():
    """Test code interpreter with SmolAgents integration"""
    tool = CodeInterpreterTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert tool.name == "code_interpreter"
    assert tool.description
    assert tool.inputs
    assert tool.output_type == "string"
    
    # Test code execution
    code = """
    def greet(name):
        return f"Hello, {name}!"
    print(greet("World"))
    """
    result = await tool.forward(code=code)
    assert isinstance(result, str)
    assert "Hello, World!" in result

@pytest.mark.asyncio
async def test_mock_web_search():
    """Test mock web search with SmolAgents integration"""
    tool = MockWebSearchTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert tool.inputs["query"]["type"] == "string"
    assert tool.output_type == "string"
    
    # Test search
    result = await tool.forward(query="quantum computing")
    assert isinstance(result, str)
    assert "IBM" in result
    assert "Google" in result

@pytest.mark.asyncio
async def test_mock_file_handler():
    """Test mock file handler with SmolAgents integration"""
    tool = MockFileHandlerTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert "action" in tool.inputs
    assert "path" in tool.inputs
    assert "content" in tool.inputs
    assert tool.output_type == "string"
    
    # Test write and read
    write_result = await tool.forward(
        action="write",
        path="test.txt",
        content="Test content"
    )
    assert isinstance(write_result, str)
    assert "success" in write_result.lower()
    
    read_result = await tool.forward(
        action="read",
        path="test.txt"
    )
    assert isinstance(read_result, str)
    assert "Test content" in read_result

@pytest.mark.asyncio
async def test_mock_apa_formatter():
    """Test mock APA formatter with SmolAgents integration"""
    tool = MockAPAFormatterTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert tool.inputs["text"]["type"] == "string"
    assert tool.output_type == "string"
    
    # Test formatting
    result = await tool.forward(text="Test research paper")
    assert isinstance(result, str)
    assert "Title:" in result
    assert "Authors:" in result

@pytest.mark.asyncio
async def test_mock_weather():
    """Test mock weather tool with SmolAgents integration"""
    tool = MockWeatherTool()
    
    # Verify SmolAgents attributes
    assert isinstance(tool, Tool)
    assert tool.inputs["city"]["type"] == "string"
    assert tool.output_type == "string"
    
    # Test forecast
    result = await tool.forward(city="boston")
    assert isinstance(result, str)
    assert "Cloudy" in result
    assert "45°F" in result
