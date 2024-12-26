"""Tests for GLUE Expression System"""

import pytest
from typing import Dict, Any
from src.glue.expressions.core import field, magnet, magnetize
from src.glue.core.resource import Resource, ResourceState
from src.glue.tools.base import BaseTool, ToolConfig, ToolPermission

# ==================== Test Tools ====================
class TestTool(BaseTool):
    """Simple tool for testing expressions"""
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

# ==================== Field Tests ====================

async def test_field_context():
    """Test field context with registry"""
    async with field("test_field") as f:
        # Field should be active
        assert f.name == "test_field"
        assert f._active
        
        # Add resources
        tool1 = TestTool("tool1")
        tool2 = TestTool("tool2")
        
        await f.add_resource(tool1)
        await f.add_resource(tool2)
        
        # Test registry integration
        assert f.get_resource("tool1") == tool1
        assert f.get_resource("tool2") == tool2
        
        # Test attraction
        await f.attract(tool1, tool2)
        assert tool2 in tool1._attracted_to
        assert tool1 in tool2._attracted_to
    
    # Field should be cleaned up
    assert not f._active
    assert not f._resources

async def test_field_decorator():
    """Test field decorator usage"""
    results = []
    
    @field("test_field")
    async def test_func(f):
        # Field should be active
        assert f.name == "test_field"
        assert f._active
        
        # Add resource
        tool = TestTool()
        await f.add_resource(tool)
        results.append(tool)
    
    await test_func()
    
    # Field should be cleaned up
    tool = results[0]
    assert tool.field is None
    assert tool.state == ResourceState.IDLE

# ==================== Magnet Tests ====================

def test_magnet_basic():
    """Test basic magnet configuration"""
    config = magnet("test")
    
    assert config["name"] == "test"
    assert config["magnetic"] is True
    assert config["__magnet__"] is True  # API compatibility
    assert "magnetic" in config["tags"]

def test_magnet_sticky():
    """Test sticky magnet configuration"""
    config = magnet("test", sticky=True)
    
    assert config["sticky"] is True
    assert "sticky" in config["tags"]

def test_magnet_shared_resources():
    """Test shared resources configuration"""
    shared = ["data", "result"]
    config = magnet("test", shared_resources=shared)
    
    assert config["shared_resources"] == shared

def test_magnet_tags():
    """Test custom tags"""
    tags = {"custom", "test"}
    config = magnet("test", tags=tags)
    
    assert "magnetic" in config["tags"]
    assert tags.issubset(config["tags"])

# ==================== Magnetize Tests ====================

def test_magnetize_list():
    """Test magnetizing list of tools"""
    tools = ["tool1", "tool2"]
    result = magnetize(tools)
    
    assert len(result) == 2
    for name in tools:
        assert name in result
        assert result[name]["magnetic"] is True
        assert result[name]["__magnet__"] is True
        assert "magnetic" in result[name]["tags"]

def test_magnetize_dict():
    """Test magnetizing dict of tools"""
    tools = {
        "tool1": {"sticky": True},
        "tool2": {"shared_resources": ["data"]}
    }
    result = magnetize(tools)
    
    assert len(result) == 2
    assert result["tool1"]["sticky"] is True
    assert "sticky" in result["tool1"]["tags"]
    assert result["tool2"]["shared_resources"] == ["data"]

def test_magnetize_shared_resources():
    """Test shared resources in magnetize"""
    tools = ["tool1", "tool2"]
    shared = ["data", "result"]
    result = magnetize(tools, shared_resources=shared)
    
    for config in result.values():
        assert config["shared_resources"] == shared

# ==================== Integration Tests ====================

async def test_magnetic_tool_integration():
    """Test magnetic tool in field"""
    async with field("test_field") as f:
        # Create magnetic tool
        config = magnet(
            "test_tool",
            sticky=True,
            shared_resources=["data"]
        )
        tool = TestTool(**config)
        
        await f.add_resource(tool)
        
        # Verify magnetic properties
        assert "magnetic" in tool.metadata.tags
        assert "sticky" in tool.metadata.tags
        assert tool.magnetic is True
        assert tool.sticky is True
        assert tool.shared_resources == ["data"]
        
        # Test execution
        result = await tool.execute(test=True)
        assert result["count"] == 1
        assert result["args"]["test"] is True

async def test_magnetic_tool_sharing():
    """Test resource sharing between magnetic tools"""
    async with field("test_field") as f:
        # Create magnetic tools
        tool1 = TestTool(**magnet("tool1", shared_resources=["data"]))
        tool2 = TestTool(**magnet("tool2", shared_resources=["data"]))
        
        await f.add_resource(tool1)
        await f.add_resource(tool2)
        await f.attract(tool1, tool2)
        
        # Test resource sharing
        test_data = "shared data"
        if hasattr(tool1, "data"):
            tool1.data = test_data
            assert tool2.data == test_data
        
        # Test execution maintains sharing
        await tool1.execute()
        assert tool2 in tool1._attracted_to
        assert tool1 in tool2._attracted_to
