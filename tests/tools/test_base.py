# tests/tools/test_base.py

# ==================== Imports ====================
import pytest
from typing import Any
from src.glue.tools.base import (
    BaseTool,
    ToolConfig,
    ToolPermission,
    ToolRegistry
)

# ==================== Mock Tools ====================
class MockTool(BaseTool):
    """Mock tool for testing"""
    async def _execute(self, **kwargs) -> Any:
        return "mock_result"

class ErrorTool(BaseTool):
    """Tool that raises an error"""
    async def _execute(self, **kwargs) -> Any:
        raise ValueError("Test error")

# ==================== Fixtures ====================
@pytest.fixture
def mock_tool():
    return MockTool(
        name="mock_tool",
        description="A mock tool for testing",
        config=ToolConfig(
            required_permissions=[ToolPermission.READ]
        )
    )

@pytest.fixture
def tool_registry():
    return ToolRegistry()

# ==================== Tool Tests ====================
def test_tool_initialization(mock_tool):
    """Test basic tool initialization"""
    assert mock_tool.name == "mock_tool"
    assert mock_tool.description == "A mock tool for testing"
    assert ToolPermission.READ in mock_tool.config.required_permissions

@pytest.mark.asyncio
async def test_tool_execution(mock_tool):
    """Test tool execution"""
    result = await mock_tool.safe_execute()
    assert result == "mock_result"
    assert mock_tool._is_initialized

@pytest.mark.asyncio
async def test_error_handling():
    """Test tool error handling"""
    error_tool = ErrorTool("error_tool", "A tool that errors")
    
    # Add error handler
    async def handle_error(e):
        return "handled_error"
    
    error_tool.add_error_handler(ValueError, handle_error)
    
    result = await error_tool.safe_execute()
    assert result == "handled_error"

def test_permission_validation(mock_tool):
    """Test permission validation"""
    assert mock_tool.validate_permissions([ToolPermission.READ])
    assert not mock_tool.validate_permissions([ToolPermission.WRITE])

# ==================== Registry Tests ====================
def test_registry_registration(tool_registry, mock_tool):
    """Test tool registration"""
    tool_registry.register(mock_tool)
    assert mock_tool.name in tool_registry.list_tools()
    assert tool_registry.get_tool(mock_tool.name) == mock_tool

def test_registry_unregistration(tool_registry, mock_tool):
    """Test tool unregistration"""
    tool_registry.register(mock_tool)
    tool_registry.unregister(mock_tool.name)
    assert mock_tool.name not in tool_registry.list_tools()

@pytest.mark.asyncio
async def test_registry_execution(tool_registry, mock_tool):
    """Test tool execution through registry"""
    tool_registry.register(mock_tool)
    tool_registry.grant_permissions(
        mock_tool.name,
        [ToolPermission.READ]
    )
    
    result = await tool_registry.execute_tool(mock_tool.name)
    assert result == "mock_result"

@pytest.mark.asyncio
async def test_registry_permission_error(tool_registry, mock_tool):
    """Test permission error handling"""
    tool_registry.register(mock_tool)
    # Don't grant required READ permission
    
    with pytest.raises(PermissionError):
        await tool_registry.execute_tool(mock_tool.name)

def test_registry_tool_listing(tool_registry, mock_tool):
    """Test tool listing"""
    tool_registry.register(mock_tool)
    tools = tool_registry.list_tools()
    assert len(tools) == 1
    assert mock_tool.name in tools

def test_registry_tool_description(tool_registry, mock_tool):
    """Test getting tool description"""
    tool_registry.register(mock_tool)
    description = tool_registry.get_tool_description(mock_tool.name)
    assert mock_tool.name in description
    assert mock_tool.description in description

@pytest.mark.asyncio
async def test_tool_cleanup(mock_tool):
    """Test tool cleanup"""
    await mock_tool.initialize()
    assert mock_tool._is_initialized
    
    await mock_tool.cleanup()
    assert not mock_tool._is_initialized

@pytest.mark.asyncio
async def test_nonexistent_tool_execution(tool_registry):
    """Test executing nonexistent tool"""
    with pytest.raises(ValueError):
        await tool_registry.execute_tool("nonexistent_tool")
