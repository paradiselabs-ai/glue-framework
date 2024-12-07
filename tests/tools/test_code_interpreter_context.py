# tests/tools/test_code_interpreter_context.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
from typing import Dict, List
from src.glue.tools.code_interpreter import CodeInterpreterTool
from src.glue.core.context import ContextState, InteractionType, ComplexityLevel
from src.glue.magnetic.field import MagneticField

# ==================== Test Data ====================
SIMPLE_CODE = """
print('Hello, World!')
"""

MODERATE_CODE = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))
"""

COMPLEX_CODE = """
class BinarySearchTree:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None

    def insert(self, value):
        if value < self.value:
            if self.left is None:
                self.left = BinarySearchTree(value)
            else:
                self.left.insert(value)
        else:
            if self.right is None:
                self.right = BinarySearchTree(value)
            else:
                self.right.insert(value)

# Create and test BST
bst = BinarySearchTree(5)
for val in [3, 7, 1, 4, 6, 8]:
    bst.insert(val)
"""

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def context_aware_interpreter():
    """Create a context-aware code interpreter"""
    tool = CodeInterpreterTool(
        name="test_interpreter",
        description="Test interpreter",
        magnetic=True
    )
    await tool.initialize()
    return tool

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
    simple_result = await context_aware_interpreter.analyze_complexity(SIMPLE_CODE)
    assert simple_result == ComplexityLevel.SIMPLE
    
    # Moderate code
    moderate_result = await context_aware_interpreter.analyze_complexity(MODERATE_CODE)
    assert moderate_result == ComplexityLevel.MODERATE
    
    # Complex code
    complex_result = await context_aware_interpreter.analyze_complexity(COMPLEX_CODE)
    assert complex_result == ComplexityLevel.COMPLEX

@pytest.mark.asyncio
async def test_context_based_execution(context_aware_interpreter, simple_context, complex_context):
    """Test execution behavior in different contexts"""
    # Simple context should execute immediately
    simple_result = await context_aware_interpreter.execute(
        SIMPLE_CODE,
        context=simple_context
    )
    assert simple_result["success"]
    assert not simple_result.get("warnings")
    
    # Complex context should add safety checks
    complex_result = await context_aware_interpreter.execute(
        COMPLEX_CODE,
        context=complex_context
    )
    assert complex_result["success"]
    assert "safety_checks" in complex_result
    assert complex_result["safety_checks"]["memory_limit"]
    assert complex_result["safety_checks"]["time_limit"]

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
    os.system('rm -rf /')
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
    # First execution
    first_result = await context_aware_interpreter.execute(
        COMPLEX_CODE,
        context=complex_context
    )
    assert first_result["success"]
    
    # Second execution should have access to previous context
    second_code = """
    # This should have access to the previous BST
    print(bst.value)
    """
    second_result = await context_aware_interpreter.execute(
        second_code,
        context=complex_context
    )
    assert second_result["success"]
    assert "5" in second_result["output"]  # Original BST root value

@pytest.mark.asyncio
async def test_magnetic_field_context(context_aware_interpreter, complex_context):
    """Test magnetic field integration with context"""
    # Create a field and add the interpreter
    async with MagneticField("test_field") as field:
        await field.add_resource(context_aware_interpreter)
        
        # Execute code that produces a result
        first_code = """
        result = 42
        print(result)
        """
        first_result = await context_aware_interpreter.execute(
            first_code,
            context=complex_context
        )
        assert first_result["success"]
        
        # Result should be available in the field
        assert field.get_resource("result") == 42
        
        # Other tools should be able to access it
        other_tool = CodeInterpreterTool(
            name="other_interpreter",
            description="Other interpreter",
            magnetic=True
        )
        await field.add_resource(other_tool)
        await other_tool.initialize()
        
        assert other_tool.get_shared_resource("result") == 42

@pytest.mark.asyncio
async def test_context_based_error_handling(context_aware_interpreter, simple_context, complex_context):
    """Test error handling in different contexts"""
    # Simple context should provide basic error info
    error_code = """
    x = undefined_variable
    """
    simple_result = await context_aware_interpreter.execute(
        error_code,
        context=simple_context
    )
    assert not simple_result["success"]
    assert "error" in simple_result
    assert isinstance(simple_result["error"], str)  # Basic error message
    
    # Complex context should provide detailed error info
    complex_result = await context_aware_interpreter.execute(
        error_code,
        context=complex_context
    )
    assert not complex_result["success"]
    assert "error" in complex_result
    assert "traceback" in complex_result  # Detailed traceback
    assert "suggestions" in complex_result  # Error fix suggestions

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
    os.system('echo "Hello"')
    """
    security_validation = await context_aware_interpreter.validate_code(
        security_code,
        context=complex_context
    )
    assert not security_validation["valid"]
    assert any(warning["type"] == "security" for warning in security_validation["warnings"])
