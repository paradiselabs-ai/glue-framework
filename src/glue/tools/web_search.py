"""Web search tool implementation"""

from typing import Any, Dict, Optional
from smolagents import Tool

class WebSearchTool(Tool):
    """Tool for performing web searches"""
    
    def __init__(self):
        self.name = "web_search"
        self.description = "Search the web for information"
        self.inputs = {
            "query": {
                "type": "string",
                "description": "The search query to execute"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 3)",
                "nullable": True
            }
        }
        self.output_type = "string"
        
    async def forward(self, query: str, num_results: int = 3) -> str:
        """Execute web search"""
        try:
            # Use SERP API for search
            from .search_providers.serp import search_web
            results = await search_web(query, num_results)
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(
                    f"Title: {result['title']}\n"
                    f"URL: {result['url']}\n"
                    f"Snippet: {result['snippet']}\n"
                )
                
            return "\n\n".join(formatted_results)
            
        except Exception as e:
            return f"Search failed: {str(e)}"
