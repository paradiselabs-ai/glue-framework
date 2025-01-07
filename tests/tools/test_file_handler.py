# tests/tools/test_file_handler.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
import tempfile
from src.glue.tools.file_handler import FileHandlerTool
from src.glue.tools.magnetic import ResourceLockedException, ResourceStateException
from src.glue.magnetic.field import MagneticField
from src.glue.core.types import ResourceState
from src.glue.core.binding import AdhesiveType
from src.glue.core.registry import ResourceRegistry

# ==================== Test Data ====================
TEST_CONTENT = "Hello, World!"
TEST_JSON = {"message": "Hello, World!"}
TEST_YAML = {"greeting": {"message": "Hello, World!"}}
TEST_CSV = [{"name": "John", "age": "30"}, {"name": "Jane", "age": "25"}]

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def temp_dir():
    """Create a temporary directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest_asyncio.fixture
async def file_handler(temp_dir):
    """Create a file handler tool"""
    tool = FileHandlerTool(
        name="test_handler",
        description="Test file handler",
        base_path=temp_dir
    )
    yield tool

@pytest_asyncio.fixture
async def registry():
    """Create a resource registry"""
    return ResourceRegistry()

@pytest_asyncio.fixture
async def field(registry):
    """Create a magnetic field"""
    async with MagneticField("test_field", registry) as field:
        yield field

@pytest_asyncio.fixture
async def tool_in_field(file_handler, field):
    """Create a tool and add it to a field"""
    await field.add_resource(file_handler)
    await file_handler.initialize()
    await file_handler.enter_field(field)
    return file_handler

# ==================== Tests ====================
def test_initialization():
    """Test tool initialization"""
    tool = FileHandlerTool(
        name="test_handler",
        description="Test file handler",
        binding_type=AdhesiveType.GLUE
    )
    
    assert tool.name == "test_handler"
    assert tool.description == "Test file handler"
    assert tool.binding_type == AdhesiveType.GLUE
    assert tool._state == ResourceState.IDLE
    assert not tool._is_initialized
    assert ".txt" in tool.allowed_formats

@pytest.mark.asyncio
async def test_execution_without_field(file_handler):
    """Test execution fails without field"""
    await file_handler.initialize()
    with pytest.raises(ResourceStateException):
        await file_handler.execute(
            operation="write",
            file_path="test.txt",
            content=TEST_CONTENT
        )

@pytest.mark.asyncio
async def test_execution_in_field(tool_in_field):
    """Test normal execution in field"""
    # Write file
    result = await tool_in_field.execute(
        operation="write",
        file_path="test.txt",
        content=TEST_CONTENT
    )
    assert result["success"]
    assert tool_in_field._state == ResourceState.IDLE
    
    # Read file
    result = await tool_in_field.execute(
        operation="read",
        file_path="test.txt"
    )
    assert result["success"]
    assert result["content"] == TEST_CONTENT

@pytest.mark.asyncio
async def test_locked_execution(tool_in_field):
    """Test execution fails when locked"""
    # Lock the tool
    holder = FileHandlerTool(
        name="holder",
        description="Holder tool"
    )
    await tool_in_field.lock(holder)
    
    # Try to execute
    with pytest.raises(ResourceLockedException):
        await tool_in_field.execute(
            operation="write",
            file_path="test.txt",
            content=TEST_CONTENT
        )

@pytest.mark.asyncio
async def test_shared_execution(field):
    """Test execution with shared resources"""
    # Create and add tools
    tool1 = FileHandlerTool(
        name="handler1",
        description="First handler"
    )
    tool2 = FileHandlerTool(
        name="handler2",
        description="Second handler"
    )
    await field.add_resource(tool1)
    await field.add_resource(tool2)
    await tool1.initialize()
    await tool2.initialize()
    await tool1.enter_field(field)
    await tool2.enter_field(field)
    
    # Create attraction
    await field.attract(tool1, tool2)
    
    # Execute tool1
    result = await tool1.execute(
        operation="write",
        file_path="test.txt",
        content=TEST_CONTENT
    )
    assert result["success"]
    assert tool1._state == ResourceState.SHARED

@pytest.mark.asyncio
async def test_format_handling(tool_in_field):
    """Test handling different file formats"""
    # Test JSON
    json_result = await tool_in_field.execute(
        operation="write",
        file_path="test.json",
        content=TEST_JSON
    )
    assert json_result["success"]
    
    # Test YAML
    yaml_result = await tool_in_field.execute(
        operation="write",
        file_path="test.yaml",
        content=TEST_YAML
    )
    assert yaml_result["success"]
    
    # Test CSV
    csv_result = await tool_in_field.execute(
        operation="write",
        file_path="test.csv",
        content=TEST_CSV
    )
    assert csv_result["success"]

@pytest.mark.asyncio
async def test_file_operations(tool_in_field):
    """Test various file operations"""
    # Write
    write_result = await tool_in_field.execute(
        operation="write",
        file_path="test.txt",
        content=TEST_CONTENT
    )
    assert write_result["success"]
    
    # Read
    read_result = await tool_in_field.execute(
        operation="read",
        file_path="test.txt"
    )
    assert read_result["success"]
    assert read_result["content"] == TEST_CONTENT
    
    # Append
    append_result = await tool_in_field.execute(
        operation="append",
        file_path="test.txt",
        content="\nAppended content"
    )
    assert append_result["success"]
    
    # Delete
    delete_result = await tool_in_field.execute(
        operation="delete",
        file_path="test.txt"
    )
    assert delete_result["success"]

@pytest.mark.asyncio
async def test_error_handling(tool_in_field):
    """Test error handling"""
    # Invalid operation
    with pytest.raises(ValueError):
        await tool_in_field.execute(
            operation="invalid",
            file_path="test.txt"
        )
    
    # Invalid format
    with pytest.raises(ValueError):
        await tool_in_field.execute(
            operation="write",
            file_path="test.invalid",
            content=TEST_CONTENT
        )
    
    # File not found
    with pytest.raises(FileNotFoundError):
        await tool_in_field.execute(
            operation="read",
            file_path="nonexistent.txt"
        )

@pytest.mark.asyncio
async def test_path_validation(tool_in_field):
    """Test path validation"""
    # Path outside base directory
    with pytest.raises(ValueError):
        await tool_in_field.execute(
            operation="write",
            file_path="../outside.txt",
            content=TEST_CONTENT
        )

@pytest.mark.asyncio
async def test_str_representation():
    """Test string representation"""
    tool = FileHandlerTool(
        name="test_handler",
        description="Test file handler",
        binding_type=AdhesiveType.GLUE,
        allowed_formats=[".txt", ".json"]
    )
    expected = (
        "test_handler: Test file handler "
        "(Magnetic Tool Binding: GLUE Shares: file_content, file_path, file_format State: IDLE)"
    )
    assert str(tool) == expected
