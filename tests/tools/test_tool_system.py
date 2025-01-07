"""Tests for GLUE Tool System"""

import pytest
import asyncio
from typing import Any
from src.glue.tools.base import (
    BaseTool,
    ToolConfig,
    ToolPermission,
    ToolRegistry
)
from src.glue.core.resource import ResourceState
from src.glue.magnetic.field import MagneticField

# ==================== Test Tool Implementation ====================
class TestTool(BaseTool):
    """Simple tool for testing"""
    def __init__(self, name: str = "test_tool"):
        super().__init__(
            name=name,
            description="Test tool implementation",
            config=ToolConfig(
                required_permissions=[ToolPermission.EXECUTE]
            )
        )
        self.execution_count = 0
        self.last_args = None

    async def _execute(self, **kwargs) -> Any:
        self.execution_count += 1
        self.last_args = kwargs
        return {"count": self.execution_count, "args": kwargs}

# ==================== Tool Tests ====================

@pytest.mark.asyncio
async def test_tool_basic():
    """Test basic tool functionality"""
    tool = TestTool()
    
    # Test initialization
    assert tool.name == "test_tool"
    assert tool.state == ResourceState.IDLE
    assert "tool" in tool.metadata.tags
    assert tool.metadata.category == "tool"
    
    # Test execution
    result = await tool.execute(test_arg="value")
    assert result["count"] == 1
    assert result["args"]["test_arg"] == "value"
    assert tool.state == ResourceState.IDLE  # Should return to IDLE
    
    # Test busy state
    tool._state = ResourceState.ACTIVE
    with pytest.raises(RuntimeError):
        await tool.execute()

@pytest.mark.asyncio
async def test_tool_error_handling():
    """Test tool error handling"""
    tool = TestTool()
    
    # Add error handler
    test_result = {"handled": False}
    def handle_error(error):
        test_result["handled"] = True
        return {"error_handled": str(error)}
    
    tool.add_error_handler(ValueError, handle_error)
    
    # Test normal execution
    result = await tool.safe_execute(valid=True)
    assert result["count"] == 1
    assert not test_result["handled"]
    
    # Test error handling
    async def failing_execute(**kwargs):
        raise ValueError("Test error")
    
    tool._execute = failing_execute
    result = await tool.safe_execute()
    assert test_result["handled"]
    assert "error_handled" in result

@pytest.mark.asyncio
async def test_tool_permissions():
    """Test tool permission system"""
    tool = TestTool()
    
    # Test permission validation
    assert not tool.validate_permissions([])
    assert tool.validate_permissions([ToolPermission.EXECUTE])
    assert tool.validate_permissions([
        ToolPermission.EXECUTE,
        ToolPermission.READ
    ])

@pytest.mark.asyncio
async def test_tool_field_integration():
    """Test tool integration with magnetic field"""
    registry = ToolRegistry()
    field = MagneticField("test_field", registry)
    
    tool1 = TestTool("tool1")
    tool2 = TestTool("tool2")
    
    async with field:
        # Add tools to field
        await field.add_resource(tool1)
        await field.add_resource(tool2)
        
        # Test attraction
        success = await field.attract(tool1, tool2)
        assert success
        assert tool2 in tool1._attracted_to
        assert tool1 in tool2._attracted_to
        
        # Test execution maintains field state
        result = await tool1.execute(test=True)
        assert result["count"] == 1
        assert tool2 in tool1._attracted_to  # Attraction should remain
        
        # Test cleanup
        await field.remove_resource(tool1)
        assert tool1._current_field is None
        assert not tool1._attracted_to

# ==================== Registry Tests ====================

@pytest.mark.asyncio
async def test_tool_registry_basic():
    """Test basic tool registry functionality"""
    registry = ToolRegistry()
    tool = TestTool()
    
    # Test registration
    registry.register_tool(tool)
    assert registry.get_tool("test_tool") == tool
    
    # Test tool listing
    tools = registry.list_tools()
    assert "test_tool" in tools
    
    # Test description
    desc = registry.get_tool_description("test_tool")
    assert "Test tool implementation" in desc
    
    # Test unregistration
    registry.unregister_tool("test_tool")
    assert registry.get_tool("test_tool") is None

@pytest.mark.asyncio
async def test_tool_registry_permissions():
    """Test tool registry permission management"""
    registry = ToolRegistry()
    tool = TestTool()
    registry.register_tool(tool)
    
    # Test permission granting
    registry.grant_permissions("test_tool", [ToolPermission.EXECUTE])
    perms = registry.get_tool_permissions("test_tool")
    assert ToolPermission.EXECUTE in perms
    
    # Test execution with permissions
    result = await registry.execute_tool("test_tool", test=True)
    assert result["count"] == 1
    
    # Test execution without permissions
    registry.grant_permissions("test_tool", [])
    with pytest.raises(PermissionError):
        await registry.execute_tool("test_tool")

@pytest.mark.asyncio
async def test_concurrent_tool_execution():
    """Test concurrent tool execution"""
    registry = ToolRegistry()
    tool = TestTool()
    registry.register_tool(tool)
    registry.grant_permissions("test_tool", [ToolPermission.EXECUTE])
    
    # Create concurrent executions
    async def execute_task(i: int) -> Any:
        return await registry.execute_tool("test_tool", task_id=i)
    
    tasks = [execute_task(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    
    # Verify all executions completed
    assert len(results) == 5
    assert tool.execution_count == 5
    
    # Verify state
    assert tool.state == ResourceState.IDLE
