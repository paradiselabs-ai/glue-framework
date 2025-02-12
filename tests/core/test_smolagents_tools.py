"""Test SmolAgents tool integration"""

import pytest
from smolagents import Tool
from glue.tools.file_handler import FileHandlerTool
from glue.tools.web_search import WebSearchTool
from glue.tools.code_interpreter import CodeInterpreterTool

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
