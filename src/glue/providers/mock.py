"""Mock provider for testing"""

from typing import Dict, Any, Optional
from ..core.types import AdhesiveType
from .base import BaseProvider

class MockProvider(BaseProvider):
    """Mock provider that simulates model responses"""
    
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare mock request"""
        return {"prompt": prompt}
        
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process mock response"""
        prompt = response["prompt"].lower()
        
        # Simulate natural language tool usage
        if "research" in prompt and "quantum computing" in prompt:
            return (
                "I'll use the web search tool to find information about quantum computing "
                "and share it with the team. Let me search for recent developments."
            )
        elif "save" in prompt and "findings" in prompt:
            return (
                "I'll save these quantum computing findings to a file for your reference. "
                "Let me use the file handler to store this information."
            )
        elif "check" in prompt and "conferences" in prompt:
            return (
                "Let me quickly check for quantum computing conferences using the web search tool. "
                "This will be a one-time search."
            )
        elif "format" in prompt and "apa" in prompt:
            return (
                "I understand you need a tool for APA formatting. I can create a custom tool "
                "that formats research papers according to APA style guidelines. "
                "Let me create that tool and format the quantum computing findings."
            )
        elif "weather" in prompt:
            return (
                "I'll use the weather tool from our MCP server to check the conditions "
                "in those quantum research hubs."
            )
        else:
            return "I'm not sure how to help with that specific request."
            
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock making a request"""
        return request_data
        
    async def _handle_error(self, error: Exception) -> None:
        """Handle mock errors"""
        pass
