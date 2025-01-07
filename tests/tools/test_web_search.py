# tests/tools/test_web_search.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
import aiohttp
from typing import Dict
from src.glue.tools.web_search import WebSearchTool
from src.glue.tools.magnetic import ResourceLockedException, ResourceStateException
from src.glue.magnetic.field import MagneticField
from src.glue.core.types import ResourceState
from src.glue.core.binding import AdhesiveType
from src.glue.core.registry import ResourceRegistry

# ==================== Mock Classes ====================
class MockResponse:
    """Mock aiohttp response"""
    def __init__(self, data: Dict):
        self.data = data
        
    async def json(self, content_type=None):
        return self.data
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, *args):
        pass
        
    def raise_for_status(self):
        pass

class MockClientSession:
    """Mock aiohttp client session"""
    def __init__(self, response_data: Dict):
        self.response_data = response_data
        self.closed = False
        
    async def get(self, url: str, params: Dict = None, **kwargs) -> MockResponse:
        # Return mock response directly
        return MockResponse(self.response_data)
        
    async def close(self):
        self.closed = True

# ==================== Test Data ====================
MOCK_SEARCH_RESULTS = {
    "RelatedTopics": [
        {
            "Text": "Python - Programming language",
            "FirstURL": "https://python.org"
        },
        {
            "Text": "Django - Web framework",
            "FirstURL": "https://djangoproject.com"
        }
    ]
}

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def search_tool():
    """Create a web search tool"""
    tool = WebSearchTool(
        api_key="test_key",
        name="test_search",
        description="Test search tool"
    )
    yield tool
    if tool._session:
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
async def tool_in_field(search_tool, field):
    """Create a tool and add it to a field"""
    await field.add_resource(search_tool)
    await search_tool.initialize()
    await search_tool.enter_field(field)
    return search_tool

@pytest_asyncio.fixture
async def mock_session():
    """Create a mock session with test data"""
    session = MockClientSession(MOCK_SEARCH_RESULTS)
    yield session
    await session.close()

# ==================== Tests ====================
def test_initialization():
    """Test tool initialization"""
    tool = WebSearchTool(
        api_key="test_key",
        name="test_search",
        description="Test search tool",
        binding_type=AdhesiveType.GLUE
    )
    
    assert tool.name == "test_search"
    assert tool.description == "Test search tool"
    assert tool.binding_type == AdhesiveType.GLUE
    assert tool._state == ResourceState.IDLE
    assert not tool._is_initialized
    assert tool._session is None

@pytest.mark.asyncio
async def test_execution_without_field(search_tool, mock_session):
    """Test execution fails without field"""
    await search_tool.initialize()
    with pytest.raises(ResourceStateException):
        await search_tool.execute("test query")

@pytest.mark.asyncio
async def test_execution_in_field(tool_in_field, mock_session):
    """Test normal execution in field"""
    tool_in_field._session = mock_session
    results = await tool_in_field.execute("test query")
    
    assert len(results) == 2
    assert results[0]["title"] == "Python"
    assert results[0]["url"] == "https://python.org"
    assert tool_in_field._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_locked_execution(tool_in_field, mock_session):
    """Test execution fails when locked"""
    # Lock the tool
    holder = WebSearchTool(
        api_key="test_key",
        name="holder",
        description="Holder tool"
    )
    await tool_in_field.lock(holder)
    
    # Try to execute
    with pytest.raises(ResourceLockedException):
        await tool_in_field.execute("test query")

@pytest.mark.asyncio
async def test_shared_execution(field, mock_session):
    """Test execution with shared resources"""
    # Create and add tools
    tool1 = WebSearchTool(
        api_key="test_key",
        name="search1",
        description="First search tool"
    )
    tool2 = WebSearchTool(
        api_key="test_key",
        name="search2",
        description="Second search tool"
    )
    await field.add_resource(tool1)
    await field.add_resource(tool2)
    await tool1.initialize()
    await tool2.initialize()
    await tool1.enter_field(field)
    await tool2.enter_field(field)
    
    # Set session
    tool1._session = mock_session
    
    # Create attraction
    await field.attract(tool1, tool2)
    
    # Execute tool1
    results = await tool1.execute("test query")
    assert len(results) == 2
    assert tool1._state == ResourceState.SHARED

@pytest.mark.asyncio
async def test_cleanup(tool_in_field, mock_session):
    """Test resource cleanup"""
    # Initialize session
    tool_in_field._session = mock_session
    await tool_in_field.execute("test query")
    assert tool_in_field._session is not None
    
    # Create attraction
    other = WebSearchTool(
        api_key="test_key",
        name="other",
        description="Other tool"
    )
    field = tool_in_field._current_field
    await field.add_resource(other)
    await other.initialize()
    await other.enter_field(field)
    await field.attract(tool_in_field, other)
    
    # Store session for checking
    session = tool_in_field._session
    
    # Cleanup
    await tool_in_field.cleanup()
    
    # Check cleanup results
    assert tool_in_field._state == ResourceState.IDLE
    assert not tool_in_field._attracted_to
    assert not tool_in_field._repelled_by
    assert tool_in_field._current_field is None
    assert not tool_in_field._is_initialized
    assert tool_in_field._session is None
    assert session.closed

@pytest.mark.asyncio
async def test_session_reuse(tool_in_field, mock_session):
    """Test session is reused between executions"""
    # Set initial session
    tool_in_field._session = mock_session
    
    # First execution
    await tool_in_field.execute("query 1")
    session1 = tool_in_field._session
    
    # Second execution
    await tool_in_field.execute("query 2")
    session2 = tool_in_field._session
    
    # Should be same session
    assert session1 is session2
    assert not session1.closed

@pytest.mark.asyncio
async def test_error_handling(tool_in_field):
    """Test error handling during execution"""
    class ErrorSession:
        async def get(self, *args, **kwargs):
            raise aiohttp.ClientError("Test error")
        async def close(self):
            pass
    
    # Replace session with error session
    tool_in_field._session = ErrorSession()
    
    # Try execution
    with pytest.raises(RuntimeError) as exc:
        await tool_in_field.execute("test query")
    assert "Search request failed" in str(exc.value)
    assert tool_in_field._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_str_representation():
    """Test string representation"""
    tool = WebSearchTool(
        api_key="test_key",
        name="test_search",
        description="Test search tool",
        binding_type=AdhesiveType.GLUE
    )
    expected = (
        "test_search: Test search tool "
        "(Magnetic Tool Binding: GLUE Shares: query, search_results State: IDLE)"
    )
    assert str(tool) == expected
