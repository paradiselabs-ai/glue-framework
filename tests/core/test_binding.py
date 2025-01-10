"""Tests for GLUE binding system"""

import pytest
import pytest_asyncio
from glue.core.binding import AdhesiveType
from glue.core.resource import Resource
from glue.tools.base import BaseTool

class MockTool(BaseTool):
    """Mock tool for testing"""
    def __init__(self, name: str):
        super().__init__(name=name, description="Test tool")
        self.execute_count = 0
        self.last_context = None
    
    async def _execute(self, **kwargs):
        self.execute_count += 1
        self.last_context = kwargs.get("context")
        return {
            "result": "mock_result",
            "context": {"last_execution": self.execute_count}
        }

@pytest_asyncio.fixture
async def setup_resources():
    """Setup test resources"""
    from glue.core.registry import ResourceRegistry
    from glue.magnetic.field import MagneticField
    
    # Create registry and field
    registry = ResourceRegistry()
    field = MagneticField("test_field", registry)
    
    # Set field as active
    field._active = True
    
    # Create model with different tool bindings
    model = Resource(
        name="test_model",
        tool_bindings={
            "tape_tool": AdhesiveType.TAPE,
            "velcro_tool": AdhesiveType.VELCRO,
            "glue_tool": AdhesiveType.GLUE
        }
    )
    
    # Create tools
    tape_tool = MockTool("tape_tool")
    tape_tool.metadata.category = "tool"
    
    velcro_tool = MockTool("velcro_tool")
    velcro_tool.metadata.category = "tool"
    
    glue_tool = MockTool("glue_tool")
    glue_tool.metadata.category = "tool"
    
    # Add resources to field and registry
    await model.enter_field(field, registry)
    await tape_tool.enter_field(field, registry)
    await velcro_tool.enter_field(field, registry)
    await glue_tool.enter_field(field, registry)
    
    # Register tools
    registry.register(tape_tool, "tool")
    registry.register(velcro_tool, "tool")
    registry.register(glue_tool, "tool")
    
    yield model, tape_tool, velcro_tool, glue_tool, registry, field

    # Cleanup after yield
    await model.exit_field()
    await tape_tool.exit_field()
    await velcro_tool.exit_field()
    await glue_tool.exit_field()
    field._active = False

@pytest.mark.asyncio
async def test_tape_binding(setup_resources):
    """Test TAPE binding behavior"""
    model, tape_tool, _, _, registry, _ = setup_resources
    
    # Verify initial state
    binding = model.get_tool_binding("tape_tool")
    assert binding.type == AdhesiveType.TAPE
    assert binding.use_count == 0
    
    # Set registry explicitly before use
    model._registry = registry
    
    # Use tool
    await model.attract_to(tape_tool)
    result = await model.use_tool("tape_tool")
    
    # Verify tool executed
    assert tape_tool.execute_count == 1
    assert result["result"] == "mock_result"
    
    # Verify binding broke after use
    assert tape_tool not in model._attracted_to
    assert binding.use_count == 1

@pytest.mark.asyncio
async def test_velcro_binding(setup_resources):
    """Test VELCRO binding behavior"""
    model, _, velcro_tool, _, registry, _ = setup_resources
    
    # Verify initial state
    binding = model.get_tool_binding("velcro_tool")
    assert binding.type == AdhesiveType.VELCRO
    assert binding.use_count == 0
    
    # Set registry explicitly before use
    model._registry = registry
    
    # Use tool multiple times
    await model.attract_to(velcro_tool)
    
    result1 = await model.use_tool("velcro_tool")
    assert velcro_tool.execute_count == 1
    
    result2 = await model.use_tool("velcro_tool")
    assert velcro_tool.execute_count == 2
    
    # Verify connection maintained
    assert velcro_tool in model._attracted_to
    assert binding.use_count == 2

@pytest.mark.asyncio
async def test_glue_binding(setup_resources):
    """Test GLUE binding behavior"""
    model, _, _, glue_tool, registry, _ = setup_resources
    
    # Verify initial state
    binding = model.get_tool_binding("glue_tool")
    assert binding.type == AdhesiveType.GLUE
    assert binding.use_count == 0
    
    # Set registry explicitly before use
    model._registry = registry
    
    # Use tool and verify context persistence
    await model.attract_to(glue_tool)
    
    result1 = await model.use_tool("glue_tool")
    assert glue_tool.execute_count == 1
    assert binding.context["last_execution"] == 1
    
    result2 = await model.use_tool("glue_tool")
    assert glue_tool.execute_count == 2
    assert binding.context["last_execution"] == 2
    
    # Verify persistent connection and context
    assert glue_tool in model._attracted_to
    assert binding.use_count == 2
    assert glue_tool.last_context == binding.context

@pytest.mark.asyncio
async def test_binding_validation(setup_resources):
    """Test binding validation"""
    model, tape_tool, _, _, registry, _ = setup_resources
    
    # Set registry explicitly before use
    model._registry = registry
    
    # Try to use tool without binding
    with pytest.raises(ValueError, match="No binding found for tool"):
        await model.use_tool("unknown_tool")
    
    # Try to use tool without attraction
    with pytest.raises(ValueError, match="Tool not found - attraction required before use"):
        await model.use_tool("tape_tool")  # Not attracted yet
    
    # Verify proper attraction check
    assert not await model.attract_to(Resource("other_tool"))  # No binding configured