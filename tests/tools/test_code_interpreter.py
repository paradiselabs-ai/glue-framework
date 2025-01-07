# tests/tools/test_code_interpreter.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
from src.glue.tools.code_interpreter import CodeInterpreterTool
from src.glue.magnetic.field import MagneticField, ResourceState
from src.glue.core.registry import ResourceRegistry

# ==================== Test Data ====================
TEST_PYTHON_CODE = """
print('Hello, World!')
"""

TEST_JS_CODE = """
console.log('Hello, World!');
"""

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def interpreter():
    """Create a code interpreter tool"""
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            if "undefined_variable" in code:
                return {
                    "success": False,
                    "error": "NameError: name 'undefined_variable' is not defined",
                    "language": language
                }
            if "while True: pass" in code:
                await asyncio.sleep(2)  # Simulate long-running code
                raise TimeoutError(f"Code execution timed out after {timeout} seconds")
            if "Hello, World!" in code:
                return {"success": True, "output": "Hello, World!", "language": language}
            return {"success": True, "output": "Mock execution", "language": language}
    tool = ConcreteCodeInterpreterTool(
        name="test_interpreter",
        description="Test interpreter"
    )
    yield tool
    await tool.cleanup()

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
async def tool_in_field(interpreter, field):
    """Create a tool and add it to a field"""
    await field.add_resource(interpreter)
    await interpreter.initialize()
    await interpreter.enter_field(field)
    return interpreter

# ==================== Tests ====================
def test_initialization():
    """Test tool initialization"""
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": True, "output": "Mock execution"}

    tool = ConcreteCodeInterpreterTool(
        name="test_interpreter",
        description="Test interpreter"
    )

    assert tool.name == "test_interpreter"
    assert tool.description == "Test interpreter"
    assert tool._state == ResourceState.IDLE
    assert not tool._is_initialized
    assert "python" in tool.supported_languages

@pytest.mark.asyncio
async def test_execution_without_field():
    """Test execution fails without field"""
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": False, "error": "Mock execution failure"}

    interpreter = ConcreteCodeInterpreterTool(
        name="test_interpreter",
        description="Test interpreter"
    )
    await interpreter.initialize()
    result = await interpreter.execute(TEST_PYTHON_CODE, "python")
    assert not result["success"]
    assert "Cannot execute without magnetic field" in result["error"]

@pytest.mark.asyncio
async def test_execution_in_field(tool_in_field):
    """Test normal execution in field"""
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": True, "output": "Mock execution"}
    result = await tool_in_field.execute(TEST_PYTHON_CODE, "python")

    assert result["success"]
    assert "Hello, World!" in result["output"]
    assert tool_in_field._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_locked_execution(tool_in_field, field):
    """Test execution fails when locked"""
    # Create holder tool
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": False, "error": "Mock execution failure"}

    holder = ConcreteCodeInterpreterTool(
        name="holder",
        description="Holder tool"
    )
    await field.add_resource(holder)
    await holder.initialize()

    # Lock the tool
    await field.lock_resource(tool_in_field, holder)

    # Try to execute
    result = await tool_in_field.execute(TEST_PYTHON_CODE, "python")
    assert not result["success"]
    assert "Resource is locked" in result["error"]

@pytest.mark.asyncio
async def test_shared_execution(field):
    """Test execution with shared resources"""
    # Create and add tools
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": True, "output": "Mock execution"}

    tool1 = ConcreteCodeInterpreterTool(
        name="interpreter1",
        description="First interpreter"
    )
    tool2 = ConcreteCodeInterpreterTool(
        name="interpreter2",
        description="Second interpreter"
    )
    await field.add_resource(tool1)
    await field.add_resource(tool2)
    await tool1.initialize()
    await tool2.initialize()

    # Create attraction
    await field.attract(tool1, tool2)

    # Execute tool1
    result = await tool1.execute(TEST_PYTHON_CODE, "python")
    assert result["success"]
    assert tool1._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_chat_execution(field):
    """Test execution with chat relationship"""
    # Create and add tools
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": True, "output": "Mock execution"}

    tool1 = ConcreteCodeInterpreterTool(
        name="interpreter1",
        description="First interpreter"
    )
    tool2 = ConcreteCodeInterpreterTool(
        name="interpreter2",
        description="Second interpreter"
    )
    await field.add_resource(tool1)
    await field.add_resource(tool2)
    await tool1.initialize()
    await tool2.initialize()

    # Enable chat
    await field.enable_chat(tool1, tool2)

    # Execute tool1
    result = await tool1.execute(TEST_PYTHON_CODE, "python")
    assert result["success"]
    assert tool1._state == ResourceState.CHATTING
    assert tool2._state == ResourceState.CHATTING

@pytest.mark.asyncio
async def test_pull_execution(field):
    """Test execution with pull relationship"""
    # Create and add tools
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": True, "output": "Mock execution"}

    source = ConcreteCodeInterpreterTool(
        name="source",
        description="Source interpreter"
    )
    target = ConcreteCodeInterpreterTool(
        name="target",
        description="Target interpreter"
    )
    await field.add_resource(source)
    await field.add_resource(target)
    await source.initialize()
    await target.initialize()

    # Enable pull
    await field.enable_pull(target, source)

    # Execute source
    result = await source.execute(TEST_PYTHON_CODE, "python")
    assert result["success"]
    assert target._state == ResourceState.PULLING
    assert source in target._attracted_to

@pytest.mark.asyncio
async def test_multiple_languages(tool_in_field):
    """Test execution in different languages"""
    # Python execution
    py_result = await tool_in_field.execute(TEST_PYTHON_CODE, "python")
    assert py_result["success"]
    assert "Hello, World!" in py_result["output"]
    
    # JavaScript execution (if node is available)
    if "javascript" in tool_in_field.supported_languages:
        js_result = await tool_in_field.execute(TEST_JS_CODE, "javascript")
        assert js_result["success"]
        assert "Hello, World!" in js_result["output"]

@pytest.mark.asyncio
async def test_error_handling(tool_in_field):
    """Test error handling during execution"""
    # Invalid code
    invalid_code = "print(undefined_variable)"
    result = await tool_in_field.execute(invalid_code, "python")
    
    assert not result["success"]
    assert "NameError" in result["error"]
    assert tool_in_field._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_timeout_handling(tool_in_field):
    """Test timeout handling"""
    # Infinite loop code
    infinite_code = "while True: pass"
    
    with pytest.raises(TimeoutError):
        await tool_in_field.execute(infinite_code, "python", timeout=1.0)
    
    assert tool_in_field._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_cleanup(tool_in_field):
    """Test resource cleanup"""
    # Execute code to create temp file
    await tool_in_field.execute(TEST_PYTHON_CODE, "python")
    assert len(tool_in_field._temp_files) > 0
    
    # Create attraction
    other = CodeInterpreterTool(
        name="other",
        description="Other interpreter"
    )
    field = tool_in_field._current_field
    await field.add_resource(other)
    await other.initialize()
    await field.attract(tool_in_field, other)
    
    # Cleanup
    await tool_in_field.cleanup()
    
    # Check cleanup results
    assert tool_in_field._state == ResourceState.IDLE
    assert not tool_in_field._attracted_to
    assert not tool_in_field._repelled_by
    assert tool_in_field._current_field is None
    assert not tool_in_field._is_initialized
    assert len(tool_in_field._temp_files) == 0

@pytest.mark.asyncio
async def test_str_representation():
    """Test string representation"""
    class ConcreteCodeInterpreterTool(CodeInterpreterTool):
        async def _execute(self, code: str, language: str, context=None, timeout: float = None):
            return {"success": True, "output": "Mock execution"}

    tool = ConcreteCodeInterpreterTool(
        name="test_interpreter",
        description="Test interpreter",
        supported_languages=["python"]
    )
    expected = (
        "test_interpreter: Test interpreter "
        "(Magnetic Tool Binding: GLUE Shares: code, output, language, execution_result State: IDLE)"
    )
    assert str(tool) == expected
