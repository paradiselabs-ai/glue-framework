# src/glue/providers/openrouter.py

"""OpenRouter Provider Implementation"""

import os
import json
import aiohttp
import re
from typing import Dict, List, Any, Optional
from .base import BaseProvider
from ..core.model import ModelConfig
from ..core.logger import get_logger
from ..magnetic.field import MagneticResource

class OpenRouterProvider(BaseProvider, MagneticResource):
    """Provider for OpenRouter API"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "liquid/lfm-40b:free",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        name: Optional[str] = None  # Add name parameter for MagneticResource
    ):
        # Create model config
        config = ModelConfig(
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt
        )
        
        # Initialize base provider with model name
        BaseProvider.__init__(
            self,
            name=model,  # Use model ID for API calls
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            config=config,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Initialize magnetic resource with role name
        MagneticResource.__init__(self, name=name or model)
        
        # Store model ID separately from role name
        self.model_id = model
        
        # Ensure clean magnetic state
        self._current_field = None
        self._attracted_to = set()
        self._repelled_by = set()
        self._state = None
        
        if not self.api_key:
            raise ValueError("OpenRouter API key not found")
        
        # Initialize logger
        self.logger = get_logger()
        
        # Initialize conversation history
        self.messages: List[Dict[str, str]] = []
        if system_prompt:
            self.logger.debug(f"Initializing with system prompt: {system_prompt}")
            self.messages.append({
                "role": "system",
                "content": system_prompt
            })

    async def generate(self, prompt: str) -> str:
        """Generate a response using the provider's API and tools"""
        try:
            # Use base Model's tool analysis and execution
            tool_scores = await self._analyze_tool_needs(prompt)
            tool_results = await self._execute_tool_chain(prompt, tool_scores)
            enhanced_prompt = await self._enhance_prompt_with_results(prompt, tool_results)
            
            # Generate response using enhanced prompt
            request_data = await self._prepare_request(enhanced_prompt)
            response = await self._make_request(request_data)
            return await self._process_response(response)
            
        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

    @classmethod
    async def get_available_models(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch available models from OpenRouter API"""
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not found")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/paradiseLabs-ai/glue"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        result = await response.json()
                        raise Exception(f"OpenRouter API error: {result}")
                    
                    models = await response.json()
                    return models.get("data", [])
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error fetching models: {str(e)}")
            raise
    
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare request for OpenRouter API"""
        # Add user prompt to conversation
        self.messages.append({
            "role": "user",
            "content": prompt
        })
        
        request_data = {
            "model": self.model_id,  # Use model ID for API calls
            "messages": self.messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        # Only add optional parameters if they exist and are not None
        if hasattr(self.config, 'top_p') and self.config.top_p is not None:
            request_data["top_p"] = self.config.top_p
        if hasattr(self.config, 'presence_penalty') and self.config.presence_penalty is not None:
            request_data["presence_penalty"] = self.config.presence_penalty
        if hasattr(self.config, 'frequency_penalty') and self.config.frequency_penalty is not None:
            request_data["frequency_penalty"] = self.config.frequency_penalty
        if hasattr(self.config, 'stop_sequences') and self.config.stop_sequences:
            request_data["stop"] = self.config.stop_sequences
        
        # Log request details
        safe_data = {k: v for k, v in request_data.items() if k != "messages"}
        self.logger.debug(f"Preparing request:\n{json.dumps(safe_data, indent=2)}")
        self.logger.debug("Messages history:")
        for msg in self.messages:
            self.logger.debug(f"{msg['role']}: {msg['content']}")
        
        return request_data
    
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process response from OpenRouter API"""
        try:
            self.logger.debug(f"Processing response:\n{json.dumps(response, indent=2)}")
            
            assistant_message = response["choices"][0]["message"]
            # Add assistant response to conversation
            self.messages.append(assistant_message)
            return assistant_message["content"]
        except KeyError as e:
            self.logger.error(f"Error processing response: {str(e)}")
            self.logger.error(f"Response structure: {json.dumps(response, indent=2)}")
            raise ValueError(f"Unexpected response format: {response}")
    
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenRouter API"""
        headers = self._get_headers()
        
        try:
            async with aiohttp.ClientSession() as session:
                self.logger.debug(f"Making request to: {self.base_url}/chat/completions")
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=request_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        self.logger.error(f"API Error (Status {response.status}):")
                        self.logger.error(json.dumps(result, indent=2))
                        await self._handle_error(result)
                    
                    return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding response: {str(e)}")
            raise
    
    async def _handle_error(self, error_response: Dict[str, Any]) -> None:
        """Handle OpenRouter API errors"""
        error_message = error_response.get('error', {}).get('message', str(error_response))
        self.logger.error(f"API Error Details: {error_message}")
        raise Exception(f"OpenRouter API error: {error_message}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/paradiseLabs-ai/glue"
        }
        return headers
    
    def clear_history(self) -> None:
        """Clear conversation history"""
        self.messages = []
        if self.config.system_prompt:
            self.messages.append({
                "role": "system",
                "content": self.config.system_prompt
            })
    
    async def cleanup(self) -> None:
        """Clean up provider resources"""
        # Clear conversation history
        self.clear_history()
        
        # Clean up magnetic resources
        if self._current_field:
            try:
                await self._current_field.remove_resource(self)
            except Exception as e:
                self.logger.error(f"Error cleaning up provider: {str(e)}")
        
        self._current_field = None
        self._attracted_to.clear()
        self._repelled_by.clear()
        self._state = None
