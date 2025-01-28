"""Simplified Base Provider"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from ..core.model import ModelConfig

class SimpleBaseProvider(ABC):
    """Base class for provider implementations"""
    def __init__(
        self,
        name: str,
        api_key: str,
        config: Optional[ModelConfig] = None,
        base_url: Optional[str] = None
    ):
        # Basic provider attributes
        self.name = name
        self.category = "provider"  # For type identification
        self.api_key = api_key
        self.config = config or ModelConfig()
        self.base_url = base_url
        self._session = None

    @abstractmethod
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare the request payload for the API"""
        pass

    @abstractmethod
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process the API response into a string"""
        pass

    async def generate(self, prompt: str) -> str:
        """Generate a response using the provider's API"""
        try:
            request_data = await self._prepare_request(prompt)
            response = await self._make_request(request_data)
            return await self._process_response(response)
        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make the actual API request"""
        raise NotImplementedError("Provider must implement _make_request")

    async def _handle_error(self, error: Exception) -> None:
        """Handle provider-specific errors"""
        raise NotImplementedError("Provider must implement _handle_error")

    def _validate_api_key(self) -> bool:
        """Validate the API key format"""
        return bool(self.api_key and isinstance(self.api_key, str))

    def _get_headers(self) -> Dict[str, str]:
        """Get the common headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
