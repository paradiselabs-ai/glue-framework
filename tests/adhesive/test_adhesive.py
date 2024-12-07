# tests/adhesive/test_adhesive.py

import pytest
from src.glue.adhesive import (
    workspace, tool, tape, duct_tape,
    double_side_tape, AdhesiveType
)
from src.glue.tools.base import BaseTool

# ==================== Mock Tools ====================
class MockSearchTool(BaseTool):
    """Mock search tool for testing"""
    def __init__(self, **kwargs):
        super().__init__(name="web_search", description="Mock search")
        self.__dict__.update(kwargs)  # Allow arbitrary configuration
    
    async def execute(self, input_data):
        if isinstance(input_data, str):
            return f"results_for_{input_data}"
        return input_data
    
    def __rshift__(self, other):
        """Support >> operator"""
        return (self, other)

class MockFileHandler(BaseTool):
    """Mock file handler for testing"""
    def __init__(self, **kwargs):
        super().__init__(name="file_handler", description="Mock file handler")
        self.__dict__.update(kwargs)  # Allow arbitrary configuration
    
    async def execute(self, input_data):
        if isinstance(input_data, str):
            if input_data.startswith("results_for_"):
                return f"saved_{input_data[12:]}"  # Remove "results_for_" prefix
            return f"saved_{input_data}"
        return input_data
    
    def __rshift__(self, other):
        """Support >> operator"""
        return (self, other)

# Override tool type inference for testing
def mock_infer_tool_type(name: str) -> type:
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

# ==================== Test Data ====================
class ChainOp:
    """Chain operation wrapper"""
    def __init__(self, func):
        self.func = func
    
    async def __call__(self, *args, **kwargs):
        return await self.func(*args, **kwargs)
    
    def __rshift__(self, other):
        """Support >> operator"""
        return (self.func, other)

async def mock_process(data: str) -> str:
    return f"processed_{data}"

async def mock_error(_):
    raise ValueError("test error")

async def error_handler(error: Exception, data: str) -> str:
    return f"handled_{data}"

# Wrap functions for chaining
mock_process = ChainOp(mock_process)
mock_error = ChainOp(mock_error)
error_handler = ChainOp(error_handler)

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_workspace():
    """Test workspace context manager"""
    async with workspace("test"):
        assert True  # Workspace created successfully

@pytest.mark.asyncio
async def test_tool_creation():
    """Test simplified tool creation"""
    search = tool("web_search")
    assert isinstance(search, MockSearchTool)
    assert search.name == "web_search"

@pytest.mark.asyncio
async def test_tape_binding():
    """Test tape binding for development"""
    tools = tape([
        tool("web_search"),
        tool("file_handler")
    ])
    assert len(tools) == 2
    assert all(t._adhesive == AdhesiveType.TAPE for t in tools.values())

@pytest.mark.asyncio
async def test_double_side_tape():
    """Test sequential operations with double-sided tape"""
    search = tool("web_search")
    file = tool("file_handler")
    
    chain = double_side_tape([
        search >> file
    ])
    
    result = await chain("query")
    assert result == "saved_query"

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling with duct tape"""
    chain = double_side_tape([
        mock_error >> mock_process
    ])
    chain.add_error_handler(error_handler)
    
    result = await chain("query")
    assert result == "handled_query"

@pytest.mark.asyncio
async def test_complete_flow():
    """Test complete workflow with all concepts"""
    async with workspace("test"):
        # Create tools with tape
        tools = tape([
            tool("web_search"),
            tool("file_handler")
        ])
        
        # Create processing chain
        chain = double_side_tape([
            tools["web_search"] >> tools["file_handler"]
        ])
        
        # Add error handling
        chain.add_error_handler(error_handler)
        
        # Process data
        result = await chain("test")
        assert result == "saved_test"

@pytest.mark.asyncio
async def test_tool_configuration():
    """Test simplified tool configuration"""
    search = tool("web_search", timeout=30)
    assert hasattr(search, "timeout")
    assert search.timeout == 30

@pytest.mark.asyncio
async def test_tool_attraction():
    """Test tool attraction with double-sided tape"""
    search = tool("web_search")
    file = tool("file_handler")
    
    chain = double_side_tape([
        search >> {"memory": file}
    ])
    
    result = await chain("query")
    assert result == "saved_query"
