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
    tool
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
async def test_tool_creation():
    """Test tool creation with different bindings"""
    # Test tape binding
    tape_tools = tape([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(tape_tools) == 2
    assert all(t._adhesive == AdhesiveType.TAPE_ATTRACT for t in tape_tools.values())
    
    # Test velcro binding
    velcro_tools = velcro([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(velcro_tools) == 2
    assert all(t._adhesive == AdhesiveType.VELCRO_ATTRACT for t in velcro_tools.values())
    
    # Test glue binding
    glue_tools = glue([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(glue_tools) == 2
    assert all(t._adhesive == AdhesiveType.GLUE_ATTRACT for t in glue_tools.values())

@pytest.mark.asyncio
async def test_magnetic_flows():
    """Test magnetic flows between tools"""
    async with workspace_context("test_flows") as ws:
        # Create tools
        search = tool("web_search")
        file = tool("file_handler")
        
        await ws.add_resource(search)
        await ws.add_resource(file)
        
        # Test different flow types
        flows = [
            flow(search.name, file.name, "><", AdhesiveType.TAPE_ATTRACT),  # Bidirectional
            flow(search.name, file.name, "->", AdhesiveType.VELCRO_PUSH),  # Push
            flow(search.name, file.name, "<-", AdhesiveType.GLUE_PULL),    # Pull
            flow(search.name, file.name, "<>", AdhesiveType.TAPE_REPEL)    # Repel
        ]
        
        for f in flows:
            await ws.setup_flow(f)
            assert f in ws.flows

@pytest.mark.asyncio
async def test_tool_execution():
    """Test tool execution with magnetic flows"""
    async with workspace_context("test_execution") as ws:
        # Create tools
        search = tool("web_search")
        file = tool("file_handler")
        
        await ws.add_resource(search)
        await ws.add_resource(file)
        
        # Setup push flow from search to file
        await ws.setup_flow(flow(
            search.name,
            file.name,
            "->",
            AdhesiveType.VELCRO_PUSH
        ))
        
        # Execute search
        result = await search._execute(input_data="query")
        assert result == "results_for_query"
        
        # File should receive result
        result = await file._execute(input_data=result)
        assert result == "saved_query"

@pytest.mark.asyncio
async def test_chat_flow():
    """Test direct chat flow between tools"""
    async with workspace_context("test_chat") as ws:
        # Create tools
        search1 = tool("web_search", name="search1")
        search2 = tool("web_search", name="search2")
        
        await ws.add_resource(search1)
        await ws.add_resource(search2)
        
        # Setup chat flow
        await ws.setup_flow(flow(
            search1.name,
            search2.name,
            "<-->",
            AdhesiveType.CHAT
        ))
        
        # Verify chat mode
        assert search1._attract_mode == "chat"
        assert search2._attract_mode == "chat"

@pytest.mark.asyncio
async def test_workspace_cleanup():
    """Test workspace cleanup"""
    async with workspace_context("test_cleanup") as ws:
        # Add tools
        search = tool("web_search")
        file = tool("file_handler")
        
        await ws.add_resource(search)
        await ws.add_resource(file)
        
        # Setup flow
        await ws.setup_flow(flow(
            search.name,
            file.name,
            "><",
            AdhesiveType.TAPE_ATTRACT
        ))
    
    # After context exit
    assert ws.field is None
    assert not ws.resources
    assert not ws.flows

@pytest.mark.asyncio
async def test_concurrent_flows():
    """Test concurrent magnetic flows"""
    async with workspace_context("test_concurrent") as ws:
        # Create tools
        tools = [
            tool("web_search", name=f"search{i}")
            for i in range(3)
        ]
        
        # Add tools concurrently
        await asyncio.gather(*[
            ws.add_resource(t)
            for t in tools
        ])
        
        # Setup flows concurrently
        flows = [
            flow(tools[i].name, tools[i+1].name, "><", AdhesiveType.VELCRO_ATTRACT)
            for i in range(len(tools)-1)
        ]
        
        await asyncio.gather(*[
            ws.setup_flow(f)
            for f in flows
        ])
        
        assert len(ws.flows) == len(flows)
