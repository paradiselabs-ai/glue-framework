"""Test SmolAgents tool integration"""

import pytest
from smolagents.tools import Tool
from glue.tools.file_handler import FileHandlerTool
from glue.tools.web_search import WebSearchTool
from glue.tools.code_interpreter import CodeInterpreterTool
from glue.tools.base import ToolPermission

# Default configs for each tool type
FILE_HANDLER_CONFIG = {
    "required_permissions": [ToolPermission.FILE_SYSTEM, ToolPermission.READ, ToolPermission.WRITE],
    "tool_specific_config": {
        "workspace_dir": None,
        "base_path": None,
        "allowed_formats": None,
        "shared_resources": ["file_content", "file_path", "file_format"]
    }
}

WEB_SEARCH_CONFIG = {
    "required_permissions": [ToolPermission.NETWORK],
    "tool_specific_config": {
        "max_results": 10,
        "timeout": 30.0,
        "retry_count": 3
    }
}

CODE_INTERPRETER_CONFIG = {
    "required_permissions": [ToolPermission.EXECUTE],
    "tool_specific_config": {
        "workspace_dir": None,
        "supported_languages": None,
        "enable_security_checks": True,
        "enable_code_analysis": True,
        "enable_error_suggestions": True,
        "max_memory_mb": 500,
        "max_execution_time": 30,
        "max_file_size_kb": 10240,
        "max_subprocess_count": 2
    }
}

@pytest.mark.asyncio
async def test_file_handler_tool():
    """Test file handler with SmolAgents integration"""
    tool = FileHandlerTool(name="file_handler", config=FILE_HANDLER_CONFIG)
    
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
    tool = WebSearchTool(config=WEB_SEARCH_CONFIG)
    
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
    tool = CodeInterpreterTool(name="code_interpreter", config=CODE_INTERPRETER_CONFIG)
    
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
