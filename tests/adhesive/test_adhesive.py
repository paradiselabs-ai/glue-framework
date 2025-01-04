# tests/adhesive/test_adhesive.py

import pytest
import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional
from src.glue.adhesive import (
    AdhesiveType,
    workspace_context,
    flow,
    tape,
    velcro,
    glue,
    tool,
    bind_magnetic,
    FlowConfig
)
from src.glue.tools.base import BaseTool, ToolConfig

# ==================== Mock Tools ====================
class MockSearchTool(BaseTool):
    """Mock search tool for testing"""
    def __init__(self, **kwargs: Any) -> None:
        config = ToolConfig(required_permissions=[])
        for key, value in list(kwargs.items()):
            if hasattr(config, key):
                setattr(config, key, value)
                del kwargs[key]

        super().__init__(
            name="web_search",
            description="Mock search",
            config=config,
            permissions=None
        )
        self.__dict__.update(kwargs)
    
    async def _execute(self, **kwargs: Any) -> Any:
        input_data = kwargs.get('input_data')
        if isinstance(input_data, str):
            return f"results_for_{input_data}"
        return input_data

class MockFileHandler(BaseTool):
    """Mock file handler for testing"""
    def __init__(self, **kwargs: Any) -> None:
        config = ToolConfig(required_permissions=[])
        for key, value in list(kwargs.items()):
            if hasattr(config, key):
                setattr(config, key, value)
                del kwargs[key]

        super().__init__(
            name="file_handler",
            description="Mock file handler",
            config=config,
            permissions=None
        )
        self.__dict__.update(kwargs)
    
    async def _execute(self, **kwargs: Any) -> Any:
        input_data = kwargs.get('input_data')
        if isinstance(input_data, str):
            if input_data.startswith("results_for_"):
                return f"saved_{input_data[12:]}"
            return f"saved_{input_data}"
        return input_data

# Override tool type inference for testing
def mock_infer_tool_type(name: str) -> Optional[type]:
    """Mock tool type inference"""
    tool_types = {
        "web_search": MockSearchTool,
        "search": MockSearchTool,
        "file_handler": MockFileHandler,
        "file": MockFileHandler
    }
    return tool_types.get(name)

# Patch tool type inference
import src.glue.adhesive
src.glue.adhesive._infer_tool_type = mock_infer_tool_type

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_workspace_context():
    """Test workspace context manager"""
    async with workspace_context("test_workspace") as ws:
        # Workspace should be created
        assert ws.name == "test_workspace"
        
        # Create and add some tools
        search = tool("web_search")
        file = tool("file_handler")
        
        await ws.add_resource(search)
        await ws.add_resource(file)
        
        assert search in ws.resources.values()
        assert file in ws.resources.values()

@pytest.mark.asyncio
async def test_adhesive_types():
    """Test different adhesive types and their properties"""
    # Test tape bindings
    tape_tools = tape([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(tape_tools) == 2
    for t in tape_tools.values():
        assert t._adhesive == AdhesiveType.TAPE_ATTRACT
        assert t._break_after_use is True
        assert not hasattr(t, '_allow_reconnect')
        assert not hasattr(t, '_persist_context')
    
    # Test velcro bindings
    velcro_tools = velcro([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(velcro_tools) == 2
    for t in velcro_tools.values():
        assert t._adhesive == AdhesiveType.VELCRO_ATTRACT
        assert t._allow_reconnect is True
        assert not hasattr(t, '_break_after_use')
        assert not hasattr(t, '_persist_context')
    
    # Test glue bindings
    glue_tools = glue([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(glue_tools) == 2
    for t in glue_tools.values():
        assert t._adhesive == AdhesiveType.GLUE_ATTRACT
        assert t._persist_context is True
        assert not hasattr(t, '_break_after_use')
        assert not hasattr(t, '_allow_reconnect')

@pytest.mark.asyncio
async def test_flow_types():
    """Test different flow types and their behaviors"""
    async with workspace_context("test_flows") as ws:
        # Create tools
        search = tool("web_search")
        file = tool("file_handler")
        
        await ws.add_resource(search)
        await ws.add_resource(file)
        
        # Test bidirectional attraction
        await ws.setup_flow(flow(
            search.name, file.name, "><", AdhesiveType.TAPE_ATTRACT
        ))
        assert search._attract_mode == "bidirectional"
        assert file._attract_mode == "bidirectional"
        
        # Test push flow
        await ws.setup_flow(flow(
            search.name, file.name, "->", AdhesiveType.VELCRO_PUSH
        ))
        assert search._attract_mode == "push"
        assert file._attract_mode == "receive"
        
        # Test pull flow
        await ws.setup_flow(flow(
            search.name, file.name, "<-", AdhesiveType.GLUE_PULL
        ))
        assert search._attract_mode == "receive"
        assert file._attract_mode == "push"
        
        # Test repulsion
        await ws.setup_flow(flow(
            search.name, file.name, "<>", AdhesiveType.TAPE_REPEL
        ))
        assert search._attract_mode == "repel"
        assert file._attract_mode == "repel"
        
        # Test chat flow
        await ws.setup_flow(flow(
            search.name, file.name, "<-->", AdhesiveType.CHAT
        ))
        assert search._attract_mode == "chat"
        assert file._attract_mode == "chat"

@pytest.mark.asyncio
async def test_binding_behavior():
    """Test binding behavior and state transitions"""
    async with workspace_context("test_binding") as ws:
        # Test tape binding breaks after use
        search = tool("web_search")
        file = tool("file_handler")
        bind_magnetic(search, file, AdhesiveType.TAPE_ATTRACT)
        
        assert search._break_after_use is True
        assert file._break_after_use is True
        
        # Test velcro binding allows reconnection
        search2 = tool("web_search", name="search2")
        file2 = tool("file_handler", name="file2")
        bind_magnetic(search2, file2, AdhesiveType.VELCRO_ATTRACT)
        
        assert search2._allow_reconnect is True
        assert file2._allow_reconnect is True
        
        # Test glue binding persists context
        search3 = tool("web_search", name="search3")
        file3 = tool("file_handler", name="file3")
        bind_magnetic(search3, file3, AdhesiveType.GLUE_ATTRACT)
        
        assert search3._persist_context is True
        assert file3._persist_context is True

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent operations and state management"""
    async with workspace_context("test_concurrent") as ws:
        # Create multiple tools
        tools = [
            tool("web_search", name=f"search{i}")
            for i in range(3)
        ]
        
        # Add tools concurrently
        await asyncio.gather(*[
            ws.add_resource(t)
            for t in tools
        ])
        
        # Setup flows sequentially to ensure deterministic behavior
        await ws.setup_flow(flow(
            tools[0].name, tools[1].name, "><", AdhesiveType.TAPE_ATTRACT
        ))
        await ws.setup_flow(flow(
            tools[1].name, tools[2].name, "->", AdhesiveType.VELCRO_PUSH
        ))
        await ws.setup_flow(flow(
            tools[0].name, tools[2].name, "<>", AdhesiveType.GLUE_REPEL
        ))
        
        # Verify flow setup
        assert len(ws.flows) == 3  # Three flows were set up
        assert tools[0]._attract_mode == "bidirectional"  # From first flow
        assert tools[1]._attract_mode == "push"  # From second flow
        assert tools[2]._attract_mode == "repel"  # From third flow

@pytest.mark.asyncio
async def test_invalid_flows():
    """Test handling of invalid flow configurations"""
    async with workspace_context("test_invalid") as ws:
        search = tool("web_search")
        file = tool("file_handler")
        
        # Test invalid flow type
        with pytest.raises(ValueError):
            await ws.setup_flow(FlowConfig(
                source=search.name,
                target=file.name,
                type="invalid",
                adhesive=AdhesiveType.TAPE_ATTRACT
            ))
        
        # Test missing resources
        flow_config = flow("missing", file.name, "><", AdhesiveType.TAPE_ATTRACT)
        await ws.setup_flow(flow_config)
        assert flow_config not in ws.flows

@pytest.mark.asyncio
async def test_workspace_cleanup():
    """Test workspace cleanup and resource management"""
    async with workspace_context("test_cleanup") as ws:
        # Add tools with different bindings
        tools = {
            "tape": tool("web_search", name="tape_tool"),
            "velcro": tool("web_search", name="velcro_tool"),
            "glue": tool("web_search", name="glue_tool")
        }
        
        # Add tools and setup flows
        for t in tools.values():
            await ws.add_resource(t)
        
        await ws.setup_flow(flow(
            tools["tape"].name,
            tools["velcro"].name,
            "><",
            AdhesiveType.TAPE_ATTRACT
        ))
        
        await ws.setup_flow(flow(
            tools["velcro"].name,
            tools["glue"].name,
            "->",
            AdhesiveType.VELCRO_PUSH
        ))
    
    # Verify tool states first
    for t in tools.values():
        assert t.field is None  # Use property instead of _field
        assert not hasattr(t, "_attract_mode")
    
    # Then verify workspace cleanup
    assert ws.field is None
    assert not ws.resources
    assert not ws.flows
