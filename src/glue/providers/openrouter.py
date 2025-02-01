"""OpenRouter Provider Implementation"""

import os
import json
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional, Set
from ..core.types import AdhesiveType
from .base import BaseProvider
from ..core.model import ModelConfig
from ..core.logger import get_logger

class OpenRouterProvider(BaseProvider):
    """Provider for OpenRouter API"""
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request"""
        headers = super()._get_headers()
        headers.update({
            "HTTP-Referer": "https://github.com/paradiseLabs-ai/glue-framework",
            "Accept": "application/json",
            "X-Title": "GLUE Framework"
        })
        return headers

    def __init__(
        self,
        name: str,
        team: str,
        available_adhesives: Set[AdhesiveType],
        config: Optional[ModelConfig] = None,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.1-70b-instruct:free",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        # Create config if not provided
        if not config:
            config = ModelConfig(
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt
            )
        else:
            # Update existing config
            config.temperature = temperature
            config.max_tokens = max_tokens
            if system_prompt:
                config.system_prompt = system_prompt
        
        # Initialize base provider
        super().__init__(
            name=name,
            provider="openrouter",
            team=team,
            available_adhesives=available_adhesives,
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            config=config
        )
        self.base_url = "https://openrouter.ai/api/v1"
        # Use model from config if provided, otherwise use default
        self.model_id = config.config.get("model") if config else model
        self.logger = get_logger()
    
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare request for OpenRouter API"""
        # Get base request data from parent
        request_data = await super()._prepare_request(prompt)
        
        # Add OpenRouter-specific parameters
        request_data.update({
            "model": self.model_id,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        })
        
        return request_data
    
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process response from OpenRouter API"""
        try:
            # Handle API errors first
            if "error" in response:
                await self._handle_error(response)
            
            # Extract message and content
            content = response["choices"][0]["message"]["content"]
            return content
                
        except Exception as e:
            self.logger.error(f"Error processing response: {str(e)}")
            raise
    
    async def _handle_error(self, error: Any) -> None:
        """Handle OpenRouter API errors with fallback"""
        if isinstance(error, dict) and "error" in error:
            error_data = error["error"]
            error_msg = error_data.get("message", "Unknown API error")
            self.logger.error(f"OpenRouter API error: {error_msg}")
            
            # Try fallback model
            if self.model_id != "meta-llama/llama-3.1-8b-instruct:free":
                self.logger.info("Retrying with fallback model")
                self.model_id = "meta-llama/llama-3.1-8b-instruct:free"
                return  # Allow retry with fallback model
            
        # If fallback fails or other error, raise
        raise ValueError(f"OpenRouter API error: {error}")
    
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenRouter API"""
        headers = self._get_headers()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=request_data
            ) as response:
                result = await response.json()
                
                if response.status != 200:
                    await self._handle_error(result)
                
                return result
