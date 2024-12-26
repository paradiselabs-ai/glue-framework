# tests/providers/fixtures/provider_fixtures.py

# ==================== Imports ====================
from typing import Dict
from unittest.mock import AsyncMock

# ==================== Mock Classes ====================
class MockResponse:
    """Mock response object"""
    def __init__(self, status: int = 200, json_data: Dict = None):
        self.status = status
        self._json = json_data or {}
        self._text = "Error message" if status != 200 else ""

    async def json(self):
        return self._json

    async def text(self):
        return self._text

def create_mock_session(response_data: Dict = None, status: int = 200) -> AsyncMock:
    """Create a mock session with predefined response"""
    session = AsyncMock()
    
    # Create mock response
    response = MockResponse(status=status, json_data=response_data)
    
    # Configure the mock session's post method
    async def mock_post(*args, **kwargs):
        return response
    
    session.post = mock_post
    return session