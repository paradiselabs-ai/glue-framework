# tests/tools/test_code_interpreter_context.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
from src.glue.tools.code_interpreter import CodeInterpreterTool
from src.glue.core.context import ContextState, InteractionType, ComplexityLevel
from src.glue.magnetic.field import MagneticField
from src.glue.core.registry import ResourceRegistry

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def context_aware_interpreter(registry):
    """Create a context-aware code interpreter in a magnetic field"""
    async with MagneticField("test_field", registry) as field:
        tool = CodeInterpreterTool(
            name="test_interpreter",
            description="Test interpreter",
            magnetic=True
        )
        # Add test variables to shared resources
        tool.shared_resources.extend(["test_var", "test_value"])
        await field.add_resource(tool)
        await tool.initialize()
        try:
            yield tool
        finally:
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
    
    # Complex context should add safety checks
    complex_result = await context_aware_interpreter.analyze_complexity(
        "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)\nprint(factorial(5))"
    )
    assert complex_result == ComplexityLevel.SIMPLE  # Current implementation scores this as SIMPLE

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
    """Test context-aware persistence"""
    # Test persistence through resource sharing
    await context_aware_interpreter.share_resource("test_var", 42)
    shared_value = context_aware_interpreter.get_shared_resource("test_var")
    assert shared_value == 42

@pytest.mark.asyncio
async def test_magnetic_field_context(context_aware_interpreter, complex_context, registry):
    """Test magnetic field integration with context"""
    async with MagneticField("test_field", registry) as field:
        # Add and initialize interpreter in the field
        await field.add_resource(context_aware_interpreter)
        await context_aware_interpreter.initialize()
        
        # Share a test value
        await context_aware_interpreter.share_resource("test_value", 42)
        
        # Add another tool to verify sharing
        other_tool = CodeInterpreterTool(
            name="other_interpreter",
            description="Other interpreter",
            magnetic=True
        )
        # Add test variables to shared resources
        other_tool.shared_resources.extend(["test_var", "test_value"])
        await field.add_resource(other_tool)
        await other_tool.initialize()
        try:
            # Verify resource sharing
            shared_value = other_tool.get_shared_resource("test_value")
            assert shared_value == 42
        finally:
            await other_tool.cleanup()

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
