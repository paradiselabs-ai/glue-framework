# tests/tools/test_magnetic.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
from typing import Any
from src.glue.tools.magnetic import (
    MagneticTool,
    ResourceLockedException,
    ResourceStateException
)
from src.glue.tools.base import ToolConfig, ToolPermission
from src.glue.magnetic.field import (
    MagneticField,
    AttractionStrength,
    ResourceState
)

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def tool(TestTool):
    """Create a test tool"""
    return TestTool()

@pytest_asyncio.fixture
async def field():
    """Create a magnetic field"""
    async with MagneticField("test_field") as field:
        yield field

@pytest_asyncio.fixture
async def tool_in_field(tool, field):
    """Create a tool and add it to a field"""
    field.add_resource(tool)
    await tool.initialize()
    tool._current_field = field
    return tool

# ==================== Tests ====================
def test_initialization(TestTool):
    """Test magnetic tool initialization"""
    tool = TestTool(
        "test",
        "Test description",
        AttractionStrength.STRONG
    )
    
    # Check tool properties
    assert tool.name == "test"
    assert tool.description == "Test description"
    assert tool.strength == AttractionStrength.STRONG
    assert tool._state == ResourceState.IDLE
    assert not tool._is_initialized
    
    # Check permissions
    assert ToolPermission.MAGNETIC in tool.config.required_permissions

def test_inheritance(TestTool):
    """Test proper inheritance from both parent classes"""
    tool = TestTool()
    
    # Check instance types
    assert isinstance(tool, MagneticTool)
    assert isinstance(tool, TestTool)
    
    # Check method resolution
    assert hasattr(tool, "execute")  # From BaseTool
    assert hasattr(tool, "attract_to")  # From MagneticResource

@pytest.mark.asyncio
async def test_execution_without_field(tool):
    """Test execution fails without field"""
    await tool.initialize()
    with pytest.raises(ResourceStateException):
        await tool.execute()

@pytest.mark.asyncio
async def test_execution_in_field(tool_in_field):
    """Test normal execution in field"""
    result = await tool_in_field.execute()
    assert result == "executed"
    assert tool_in_field.execute_called
    assert tool_in_field._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_locked_execution(tool_in_field, TestTool):
    """Test execution fails when locked"""
    # Lock the tool
    holder = TestTool("holder", "Holder tool")
    await tool_in_field.lock(holder)
    
    # Try to execute
    with pytest.raises(ResourceLockedException):
        await tool_in_field.execute()

@pytest.mark.asyncio
async def test_shared_execution(field, TestTool):
    """Test execution with shared resources"""
    # Create and add tools
    tool1 = TestTool("tool1", "First tool")
    tool2 = TestTool("tool2", "Second tool")
    field.add_resource(tool1)
    field.add_resource(tool2)
    await tool1.initialize()
    await tool2.initialize()
    
    # Ensure field membership
    tool1._current_field = field
    tool2._current_field = field
    
    # Create attraction
    await field.attract(tool1, tool2)
    
    # Execute tool1
    result = await tool1.execute()
    assert result == "executed"
    assert tool1._state == ResourceState.SHARED

@pytest.mark.asyncio
async def test_state_transitions(tool_in_field, TestTool):
    """Test state transitions during execution"""
    # Initial state
    assert tool_in_field._state == ResourceState.IDLE
    
    # During normal execution
    result = await tool_in_field.execute()
    assert result == "executed"
    assert tool_in_field._state == ResourceState.IDLE
    
    # With attraction
    other = TestTool("other", "Other tool")
    field = tool_in_field._current_field
    field.add_resource(other)
    await other.initialize()
    other._current_field = field
    await field.attract(tool_in_field, other)
    
    result = await tool_in_field.execute()
    assert result == "executed"
    assert tool_in_field._state == ResourceState.SHARED

@pytest.mark.asyncio
async def test_error_handling(tool_in_field, TestTool):
    """Test state handling during errors"""
    class ErrorTool(TestTool):
        async def execute(self, **kwargs):
            await super().execute(**kwargs)
            raise ValueError("Test error")
    
    error_tool = ErrorTool("error", "Error tool")
    field = tool_in_field._current_field
    field.add_resource(error_tool)
    await error_tool.initialize()
    error_tool._current_field = field
    
    # Try execution that raises error
    with pytest.raises(ValueError):
        await error_tool.execute()
    
    # State should be reset
    assert error_tool._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_cleanup(tool_in_field, TestTool):
    """Test resource cleanup"""
    other = TestTool("other", "Other tool")
    field = tool_in_field._current_field
    field.add_resource(other)
    await other.initialize()
    other._current_field = field
    await field.attract(tool_in_field, other)
    
    # Cleanup
    await tool_in_field.cleanup()
    
    # Check cleanup results
    assert tool_in_field._state == ResourceState.IDLE
    assert not tool_in_field._attracted_to
    assert not tool_in_field._repelled_by
    assert tool_in_field._current_field is None
    assert not tool_in_field._is_initialized

@pytest.mark.asyncio
async def test_str_representation(TestTool):
    """Test string representation"""
    tool = TestTool(
        "test",
        "Test description",
        AttractionStrength.STRONG
    )
    expected = (
        "test: Test description "
        "(Magnetic Tool, Strength: STRONG, State: IDLE)"
    )
    assert str(tool) == expected

@pytest.mark.asyncio
async def test_safe_execution(tool_in_field):
    """Test safe_execute with initialization"""
    result = await tool_in_field.safe_execute()
    assert result == "executed"
    assert tool_in_field.execute_called
    assert tool_in_field._is_initialized

@pytest.mark.asyncio
async def test_error_handler(tool_in_field, TestTool):
    """Test error handler functionality"""
    error_handled = False
    
    async def handle_error(error):
        nonlocal error_handled
        error_handled = True
        return "handled"
    
    class ErrorTool(TestTool):
        async def execute(self, **kwargs):
            raise ValueError("Test error")
    
    error_tool = ErrorTool("error", "Error tool")
    error_tool.add_error_handler(ValueError, handle_error)
    
    field = tool_in_field._current_field
    field.add_resource(error_tool)
    await error_tool.initialize()
    error_tool._current_field = field
    
    result = await error_tool.safe_execute()
    assert result == "handled"
    assert error_handled
