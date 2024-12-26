# tests/providers/test_base.py

# ==================== Imports ====================
import pytest
from typing import Dict, Any
from src.glue.providers.base import BaseProvider
from src.glue.core.model import ModelConfig

# ==================== Mock Provider ====================
class MockBaseProvider(BaseProvider):
    """Mock provider for testing base functionality"""
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        return {"prompt": prompt}

    async def _process_response(self, response: Dict[str, Any]) -> str:
        return response.get("text", "")

    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"text": "test response"}

    async def _handle_error(self, error: Exception) -> None:
        raise error

# ==================== Fixtures ====================
@pytest.fixture
def base_provider():
    return MockBaseProvider(
        name="test-provider",
        api_key="test-key",
        config=ModelConfig(
            temperature=0.7,
            max_tokens=100
        )
    )

# ==================== Initialization Tests ====================
def test_provider_initialization(base_provider):
    """Test provider initialization"""
    assert base_provider.name == "test-provider"
    assert base_provider.api_key == "test-key"
    assert base_provider.provider == "MockBaseProvider"
    assert isinstance(base_provider.config, ModelConfig)

# ==================== API Key Tests ====================
def test_validate_api_key(base_provider):
    """Test API key validation"""
    assert base_provider._validate_api_key() is True
    
    # Test invalid API key
    base_provider.api_key = None
    assert base_provider._validate_api_key() is False

# ==================== Header Tests ====================
def test_get_headers(base_provider):
    """Test header generation"""
    headers = base_provider._get_headers()
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"

# ==================== Generation Tests ====================
@pytest.mark.asyncio
async def test_generate(base_provider):
    """Test generation flow"""
    response = await base_provider.generate("test prompt")
    assert response == "test response"

@pytest.mark.asyncio
async def test_generate_error():
    """Test generation error handling"""
    error_provider = MockBaseProvider(
        name="error-provider",
        api_key="test-key"
    )
    
    # Override _make_request to simulate error
    async def error_request(self, request_data):
        raise Exception("Test error")
    
    error_provider._make_request = error_request.__get__(error_provider)
    
    with pytest.raises(RuntimeError) as exc_info:
        await error_provider.generate("test prompt")
    assert "Generation failed" in str(exc_info.value)