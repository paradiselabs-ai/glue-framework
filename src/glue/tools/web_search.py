"""Web search tool implementation"""

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from prefect import task, flow
from smolagents.tools import Tool
from .base import ToolConfig, ToolPermission
from ..core.types import AdhesiveType

# Pydantic models for validation
class SearchResult(BaseModel):
    """Model for search result validation"""
    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="URL of the search result")
    snippet: str = Field(..., description="Text snippet from the search result")

class SearchConfig(BaseModel):
    """Configuration for web search tool"""
    max_results: int = Field(default=10, description="Maximum number of results to return")
    timeout: float = Field(default=30.0, description="Search timeout in seconds")
    retry_count: int = Field(default=3, description="Number of retry attempts")

class WebSearchTool(Tool):
    """Tool for performing web searches with Prefect orchestration and Pydantic validation"""
    
    # Required SmolAgents class attributes
    name = "web_search"
    description = "Search the web for information"
    skip_forward_signature_validation = True  # Using Prefect flows
    inputs = {
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
    output_type = "string"

    def __init__(
        self,
        adhesive_type: Optional[AdhesiveType] = None,
        config: Optional[SearchConfig] = None
    ):
        super().__init__()
        self.adhesive_type = adhesive_type
        self.search_config = config or SearchConfig()
        
        # Set GLUE tool configuration
        self.config = ToolConfig(
            required_permissions=[
                ToolPermission.NETWORK  # For web access
            ],
            tool_specific_config=self.search_config.model_dump()
        )

    @task(name="execute_search", retries=3, retry_delay_seconds=1)
    async def _execute_search(self, query: str, num_results: int) -> List[SearchResult]:
        """Execute search with retries using Prefect"""
        from .search_providers.serp import search_web
        results = await search_web(query, num_results)
        
        # Validate results using Pydantic
        return [SearchResult(**result) for result in results]

    @task(name="format_results")
    def _format_results(self, results: List[SearchResult]) -> str:
        """Format search results with Prefect task"""
        formatted_results = []
        for result in results:
            formatted_results.append(
                f"Title: {result.title}\n"
                f"URL: {result.url}\n"
                f"Snippet: {result.snippet}\n"
            )
        return "\n\n".join(formatted_results)

    @flow(
        name="web_search_flow",
        description="Execute web search with retries and validation",
        retries=3,
        retry_delay_seconds=1,
        persist_result=True,
        version="1.0.0"
    )
    async def forward(self, query: str, num_results: int = 3) -> str:
        """Execute web search as a Prefect flow"""
        try:
            # Ensure num_results doesn't exceed config
            num_results = min(num_results, self.search_config.max_results)
            
            # Execute search with retries
            results = await self._execute_search(query, num_results)
            
            # Format results
            return await self._format_results(results)
            
        except Exception as e:
            return f"Search failed: {str(e)}"
