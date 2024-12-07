# tests/expressions/test_expressions.py

import pytest
from src.glue.expressions import glue_app, magnet, field, magnetize, Chain
from src.glue.magnetic.field import AttractionStrength

# ==================== Test Data ====================
async def mock_model(input_data):
    return f"processed_{input_data}"

async def mock_tool(input_data):
    return f"tool_{input_data}"

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_minimal_app():
    """Test minimal app syntax"""
    @glue_app("test")
    async def test_app():
        return "success"
    
    result = await test_app()
    assert result == "success"

@pytest.mark.asyncio
async def test_field_context():
    """Test field context with minimal syntax"""
    async with field("test"):
        assert True  # Field created successfully

@pytest.mark.asyncio
async def test_field_decorator():
    """Test field as decorator"""
    @field("test")
    async def test_func():
        return "success"
    
    result = await test_func()
    assert result == "success"

@pytest.mark.asyncio
async def test_chain_operator():
    """Test >> operator for chaining"""
    chain = Chain(mock_model) >> mock_tool
    result = await chain("input")
    assert result == "tool_processed_input"

@pytest.mark.asyncio
async def test_chain_with_tools():
    """Test chain with magnetic tools"""
    memory = magnet("memory")
    chain = Chain(mock_model) >> {"memory": memory}
    result = await chain("input")
    assert result["__magnet__"]
    assert result["name"] == "memory"

@pytest.mark.asyncio
async def test_chain_parallel():
    """Test parallel operations"""
    chain = Chain(mock_model) >> [mock_tool, mock_tool]
    results = await chain("input")
    assert len(results) == 2
    assert all(r.startswith("tool_") for r in results)

@pytest.mark.asyncio
async def test_magnetize_tools():
    """Test tool magnetization with minimal syntax"""
    tools = magnetize(["tool1", "tool2"])
    assert len(tools) == 2
    assert all(t["__magnet__"] for t in tools.values())

@pytest.mark.asyncio
async def test_complete_flow():
    """Test complete expression flow"""
    @glue_app("test_flow")
    @field("test")
    async def test_app():
        # Create tools with specific configurations
        tools = magnetize({
            "memory": {"strength": "strong"},  # Added comma
            "processor": {"strength": "medium"}
        })
        
        # Create processing chain
        chain = (
            Chain(mock_model)
            >> {"memory": tools["memory"]}  # First tool attraction
            >> tools["processor"]           # Second tool attraction
        )
        
        # Execute chain
        result = await chain("input")
        return result
    
    # Run flow and verify result
    result = await test_app()
    assert isinstance(result, dict)  # Added comma
    assert result["__magnet__"]
    assert result["name"] == "processor"
    assert result["strength"] == AttractionStrength.MEDIUM

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in chains"""
    async def error_model(_):
        raise ValueError("test error")
    
    chain = Chain(error_model) >> mock_tool
    with pytest.raises(ValueError):
        await chain("input")
