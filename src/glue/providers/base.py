# src/glue/providers/base.py

# ==================== Imports ====================
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from ..core.model import Model, ModelConfig

# ==================== Base Provider Class ====================
class BaseProvider(Model, ABC):
    """Base class for all provider implementations"""
    def __init__(
        self,
        name: str,
        api_key: str,
        config: Optional[ModelConfig] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            name=name,
            provider=self.__class__.__name__,
            api_key=api_key,
            config=config
        )
        self.base_url = base_url
        self._session = None

    # ==================== Abstract Methods ====================
    @abstractmethod
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare the request payload for the API"""
        pass

    @abstractmethod
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process the API response into a string"""
        pass

    # ==================== Shared Methods ====================
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

    # ==================== Utility Methods ====================
    def _validate_api_key(self) -> bool:
        """Validate the API key format"""
        return bool(self.api_key and isinstance(self.api_key, str))

    def _get_headers(self) -> Dict[str, str]:
        """Get the common headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }