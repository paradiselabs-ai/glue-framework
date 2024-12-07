# tests/providers/test_openrouter.py

# ==================== Imports ====================
import pytest
from unittest.mock import patch, AsyncMock, Mock
from src.glue.providers.openrouter import OpenRouterProvider
from src.glue.core.model import ModelConfig
from .fixtures.provider_fixtures import create_mock_session

# ==================== Fixtures ====================
@pytest.fixture
def mock_response_data():
    return {
        "choices": [{
            "message": {
                "content": "Test response content"
            }
        }]
    }

@pytest.fixture
def openrouter_provider():
    return OpenRouterProvider(
        name="test-openrouter",
        api_key="test-key",
        config=ModelConfig(
            temperature=0.7,
            max_tokens=100
        )
    )

# ==================== API Integration Tests ====================
@pytest.mark.asyncio
async def test_make_request(openrouter_provider, mock_response_data):
    """Test API request handling"""
    mock_session = create_mock_session(response_data=mock_response_data)
    openrouter_provider._session = mock_session
    
    request_data = await openrouter_provider._prepare_request("test prompt")
    response = await openrouter_provider._make_request(request_data)
    assert response == mock_response_data

@pytest.mark.asyncio
async def test_make_request_error(openrouter_provider):
    """Test API request error handling"""
    mock_session = create_mock_session(status=401)
    openrouter_provider._session = mock_session
    
    with pytest.raises(Exception):
        request_data = await openrouter_provider._prepare_request("test prompt")
        await openrouter_provider._make_request(request_data)

# ==================== End-to-End Tests ====================
@pytest.mark.asyncio
async def test_generate_success(openrouter_provider, mock_response_data):
    """Test successful generation end-to-end"""
    mock_session = create_mock_session(response_data=mock_response_data)
    openrouter_provider._session = mock_session
    
    response = await openrouter_provider.generate("test prompt")
    assert response == "Test response content"

@pytest.mark.asyncio
async def test_generate_failure(openrouter_provider):
    """Test generation failure handling"""
    mock_session = create_mock_session(status=500)
    openrouter_provider._session = mock_session
    
    with pytest.raises(RuntimeError) as exc_info:
        await openrouter_provider.generate("test prompt")
    assert "Generation failed" in str(exc_info.value)

# ==================== Cleanup Tests ====================
@pytest.mark.asyncio
async def test_cleanup(openrouter_provider):
    """Test session cleanup"""
    mock_session = AsyncMock()
    openrouter_provider._session = mock_session
    
    await openrouter_provider.cleanup()
    assert mock_session.close.called
    assert openrouter_provider._session is None