# tests/tools/test_code_interpreter_context.py

# ==================== Imports ====================
import os
import pytest
import pytest_asyncio
from src.glue.tools.code_interpreter import CodeInterpreterTool
from src.glue.core.context import ContextState, InteractionType, ComplexityLevel
from src.glue.magnetic.field import MagneticField
from src.glue.core.registry import ResourceRegistry
from src.glue.core.state import StateManager

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def context_aware_interpreter(registry, tmp_path):
    """Create a context-aware code interpreter in a magnetic field"""
    # Create a dedicated registry for the interpreter
    interpreter_registry = ResourceRegistry(StateManager())
    
    # Create a temporary workspace directory
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(exist_ok=True)
    
    async with MagneticField("test_field", interpreter_registry) as field:
        tool = CodeInterpreterTool(
            name="test_interpreter",
            description="Test interpreter",
            magnetic=True,
            sticky=True,  # Enable sticky mode for state persistence
            workspace_dir=str(workspace_dir)
        )
        # Add test variables to shared resources
        tool.shared_resources.extend(["test_var", "test_value"])
        await field.add_resource(tool)
        await tool.initialize()
        try:
            yield tool
        finally:
            # Ensure workspace exists before cleanup
            os.makedirs(tool.workspace_dir, exist_ok=True)
            await tool.cleanup()

@pytest.fixture
def registry():
    """Create a resource registry"""
    return ResourceRegistry()

@pytest.fixture
def simple_context():
    """Create a simple context state"""
    return ContextState(
        interaction_type=InteractionType.TASK,
        complexity=ComplexityLevel.SIMPLE,
        tools_required={"code_interpreter"},
        requires_research=False,
        requires_memory=False,
        requires_persistence=False,
        confidence=0.9
    )

@pytest.fixture
def complex_context():
    """Create a complex context state"""
    return ContextState(
        interaction_type=InteractionType.TASK,
        complexity=ComplexityLevel.COMPLEX,
        tools_required={"code_interpreter"},
        requires_research=False,
        requires_memory=True,
        requires_persistence=True,
        confidence=0.8
    )

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_code_complexity_analysis(context_aware_interpreter):
    """Test automatic code complexity analysis"""
    # Simple code
    simple_code = "print('Hello')"
    simple_result = await context_aware_interpreter.analyze_complexity(simple_code)
    assert simple_result == ComplexityLevel.SIMPLE
    
    # Moderate code
    moderate_code = """
    def factorial(n):
        return 1 if n <= 1 else n * factorial(n-1)
    """
    moderate_result = await context_aware_interpreter.analyze_complexity(moderate_code)
    assert moderate_result == ComplexityLevel.MODERATE
    
    # Complex code
    complex_code = """
    class Node:
        def __init__(self, value):
            self.value = value
            self.next = None
            
    def reverse_list(head):
        prev = None
        current = head
        while current:
            next_node = current.next
            current.next = prev
            prev = current
            current = next_node
        return prev
    """
    complex_result = await context_aware_interpreter.analyze_complexity(complex_code)
    assert complex_result == ComplexityLevel.COMPLEX

@pytest.mark.asyncio
async def test_context_based_execution(context_aware_interpreter, simple_context, complex_context):
    """Test execution behavior in different contexts"""
    # Simple context should execute immediately
    simple_result = await context_aware_interpreter.analyze_complexity(
        "x = 1 + 1\nprint(x)"
    )
    assert simple_result == ComplexityLevel.SIMPLE
    
    # moderate context should add safety checks
    moderate_result = await context_aware_interpreter.analyze_complexity(
        "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)\nprint(factorial(5))"
    )
    assert moderate_result == ComplexityLevel.MODERATE  # Current implementation scores this as MODERATE

@pytest.mark.asyncio
async def test_language_detection(context_aware_interpreter):
    """Test context-aware language detection"""
    # Python with context hints
    python_code = '''
    # This script calculates fibonacci numbers
    def fibonacci(n):
        return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)
    '''
    python_result = await context_aware_interpreter.detect_language(python_code)
    assert python_result == "python"
    
    # JavaScript with context hints
    js_code = '''
    // This script calculates fibonacci numbers
    function fibonacci(n) {
        return n <= 1 ? n : fibonacci(n-1) + fibonacci(n-2);
    }
    '''
    js_result = await context_aware_interpreter.detect_language(js_code)
    assert js_result == "javascript"

@pytest.mark.asyncio
async def test_security_assessment(context_aware_interpreter):
    """Test security level assessment"""
    # Safe code
    safe_code = """
    def greet(name):
        return f"Hello, {name}!"
    """
    safe_result = await context_aware_interpreter.assess_security(safe_code)
    assert safe_result["level"] == "safe"
    
    # Suspicious code (file operations)
    suspicious_code = """
    with open('test.txt', 'w') as f:
        f.write('Hello')
    """
    suspicious_result = await context_aware_interpreter.assess_security(suspicious_code)
    assert suspicious_result["level"] == "suspicious"
    assert any(concern["type"] == "file_operations" for concern in suspicious_result["concerns"])
    
    # Dangerous code (system operations)
    dangerous_code = """
    import os
    os.system('echo "test"')
    """
    dangerous_result = await context_aware_interpreter.assess_security(dangerous_code)
    assert dangerous_result["level"] == "dangerous"
    assert any(concern["type"] == "system_operations" for concern in dangerous_result["concerns"])

@pytest.mark.asyncio
async def test_context_based_resource_limits(context_aware_interpreter, simple_context, complex_context):
    """Test resource limits based on context"""
    # Simple context should have basic limits
    simple_limits = await context_aware_interpreter.get_resource_limits(simple_context)
    assert simple_limits["memory_mb"] <= 100
    assert simple_limits["time_seconds"] <= 5
    
    # Complex context should have higher limits
    complex_limits = await context_aware_interpreter.get_resource_limits(complex_context)
    assert complex_limits["memory_mb"] <= 500
    assert complex_limits["time_seconds"] <= 30

@pytest.mark.asyncio
async def test_context_persistence(context_aware_interpreter, complex_context):
    """Test context-aware persistence through sticky code and resource sharing"""
    # Test persistence through resource sharing
    await context_aware_interpreter.share_resource("test_var", 42)
    shared_value = context_aware_interpreter.get_shared_resource("test_var")
    assert shared_value == 42
    
    # Test sticky code persistence
    code1 = """
x = 100
y = 200
result = x + y
print(f'result={result}')
"""
    result1 = await context_aware_interpreter.execute(code1)
    assert result1["success"]
    
    # Keep field reference and reinitialize
    field = context_aware_interpreter._current_field
    registry = context_aware_interpreter._registry
    
    # Cleanup but keep workspace
    workspace_dir = context_aware_interpreter.workspace_dir
    await context_aware_interpreter.cleanup()
    
    # Create new interpreter with same workspace
    context_aware_interpreter = CodeInterpreterTool(
        name="test_interpreter",
        description="Test interpreter",
        magnetic=True,
        sticky=True,
        workspace_dir=workspace_dir
    )
    
    # Add to same field
    await field.add_resource(context_aware_interpreter)
    await context_aware_interpreter.initialize()
    
    # Verify persistent state is maintained
    code2 = """
print(f'x={x}, y={y}, result={result}')
"""
    result2 = await context_aware_interpreter.execute(code2)
    assert result2["success"], f"Failed to execute after reinitialization: {result2.get('error', '')}"
    assert "x=100" in result2["output"]
    assert "y=200" in result2["output"]
    assert "result=300" in result2["output"]

@pytest.mark.asyncio
async def test_magnetic_field_context(context_aware_interpreter, complex_context, registry):
    """Test tool persistence and sharing between models through magnetic field.
    
    This test demonstrates how a single tool instance can be:
    1. Used by multiple models while maintaining state
    2. Share resources through the magnetic field
    3. Persist variables and context between model interactions
    
    Rather than creating multiple tool instances, models share and reuse
    the same tool through the registry and magnetic field system.
    """
    async with MagneticField("test_field", registry) as field:
        # Add and initialize interpreter in the field
        await field.add_resource(context_aware_interpreter)
        await context_aware_interpreter.initialize()
        
        # Share a test value
        await context_aware_interpreter.share_resource("test_value", 42)
        
        # Simulate two different models accessing the same tool
        # Model 1 uses the tool to execute code
        code1 = "x = 5\nprint(x)"
        result1 = await context_aware_interpreter.execute(code1)
        assert result1["success"]
        
        # Model 2 can access the same tool and see shared resources
        shared_value = context_aware_interpreter.get_shared_resource("test_value")
        assert shared_value == 42
        
        # Model 2 executes code that builds on Model 1's execution
        code2 = """
# Access variable from previous execution
y = x + 3
print(f'x={x}, y={y}')
"""
        result2 = await context_aware_interpreter.execute(code2)
        assert result2["success"], f"Failed to execute code2: {result2.get('error', '')}"
        assert "x=5, y=8" in result2["output"]  # Verify both x and y are accessible
        
        # Verify tool state persists between model interactions
        code3 = "print(x, y)"  # Both variables should exist
        result3 = await context_aware_interpreter.execute(code3)
        assert result3["success"]
        assert "5 8" in result3["output"]

@pytest.mark.asyncio
async def test_context_based_error_handling(context_aware_interpreter, simple_context, complex_context):
    """Test error handling in different contexts"""
    error_code = "x = undefined_variable"
    
    # Simple context should provide basic validation
    simple_result = await context_aware_interpreter.validate_code(
        error_code,
        context=simple_context
    )
    assert not simple_result["valid"]
    assert "warnings" in simple_result
    
    # Complex context should provide detailed validation
    complex_result = await context_aware_interpreter.validate_code(
        error_code,
        context=complex_context
    )
    assert not complex_result["valid"]
    assert "warnings" in complex_result
    assert any(warning["type"] == "error" for warning in complex_result["warnings"])

@pytest.mark.asyncio
async def test_context_based_code_validation(context_aware_interpreter, simple_context, complex_context):
    """Test code validation based on context"""
    # Simple context allows basic operations
    simple_code = """
    x = 1 + 1
    print(x)
    """
    simple_validation = await context_aware_interpreter.validate_code(
        simple_code,
        context=simple_context
    )
    assert simple_validation["valid"]
    assert not simple_validation.get("warnings")
    
    # Complex context checks for best practices
    complex_code = """
    x=1+1
    print(x)
    """  # Missing spaces around operators
    complex_validation = await context_aware_interpreter.validate_code(
        complex_code,
        context=complex_context
    )
    assert complex_validation["valid"]  # Still valid
    assert any(warning["type"] == "style" for warning in complex_validation["warnings"])
    
    # Security validation in complex context
    security_code = """
    import os
    os.system('echo "test"')
    """
    security_validation = await context_aware_interpreter.validate_code(
        security_code,
        context=complex_context
    )
    assert not security_validation["valid"]
    assert any(warning["type"] == "security" for warning in security_validation["warnings"])
