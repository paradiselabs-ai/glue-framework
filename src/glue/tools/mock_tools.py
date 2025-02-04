"""Mock tool implementations for testing"""

from typing import Any, Dict, Optional
from smolagents import Tool

class MockWebSearchTool(Tool):
    """Mock web search tool"""
    
    def __init__(self):
        self.name = "web_search"
        self.description = "Search the web for information"
        self.inputs = {
            "query": {
                "type": "string",
                "description": "The search query to execute"
            }
        }
        self.output_type = "string"
        
    async def forward(self, query: str) -> str:
        """Execute web search"""
        if "quantum computing" in query.lower():
            return (
                "Found latest developments in quantum computing:\n"
                "1. IBM announces new 1000-qubit processor\n"
                "2. Google achieves quantum supremacy milestone\n"
                "3. New error correction techniques in quantum circuits"
            )
        elif "conferences" in query.lower():
            return (
                "Upcoming quantum computing conferences:\n"
                "- Quantum World Congress (March 15-17)\n"
                "- Q2B Conference (April 5-7)\n"
                "- IEEE Quantum Week (May 20-24)"
            )
        return f"Mock search results for: {query}"

class MockFileHandlerTool(Tool):
    """Mock file handler tool"""
    
    def __init__(self):
        self.name = "file_handler"
        self.description = "Handle file operations"
        self.inputs = {
            "action": {
                "type": "string",
                "description": "The action to perform (read/write)",
                "enum": ["read", "write"]
            },
            "path": {
                "type": "string",
                "description": "Path to the file"
            },
            "content": {
                "type": "string",
                "description": "Content to write (for write action)",
                "nullable": True
            }
        }
        self.output_type = "string"
        self._stored_data = {}
        
    async def forward(self, action: str, path: str, content: Optional[str] = None) -> str:
        """Execute file handling"""
        if action == "write":
            if content is None:
                return "Error: Content is required for write action"
            self._stored_data[path] = content
            return f"Successfully saved content to {path}"
        elif action == "read":
            return self._stored_data.get(path, f"No data found at {path}")
        else:
            return f"Invalid action: {action}"

class MockAPAFormatterTool(Tool):
    """Mock APA formatting tool"""
    
    def __init__(self):
        self.name = "apa_formatter"
        self.description = "Format text in APA style"
        self.inputs = {
            "text": {
                "type": "string",
                "description": "Text to format in APA style"
            }
        }
        self.output_type = "string"
        
    async def forward(self, text: str) -> str:
        """Execute APA formatting"""
        return (
            "Formatted in APA style:\n\n"
            "Title: Recent Developments in Quantum Computing\n"
            "Authors: Research Team\n"
            "Abstract: This paper discusses recent breakthroughs...\n\n"
            "[Content formatted according to APA 7th edition guidelines]"
        )

class MockWeatherTool(Tool):
    """Mock weather tool from MCP server"""
    
    def __init__(self):
        self.name = "weather_get_forecast"
        self.description = "Get weather forecast for a location"
        self.inputs = {
            "city": {
                "type": "string",
                "description": "City to get weather forecast for"
            }
        }
        self.output_type = "string"
        
    async def forward(self, city: str) -> str:
        """Execute weather forecast"""
        forecasts = {
            "boston": "Cloudy, 45°F",
            "copenhagen": "Light rain, 38°F",
            "tokyo": "Clear skies, 62°F"
        }
        return forecasts.get(city.lower(), f"No forecast for {city}")
