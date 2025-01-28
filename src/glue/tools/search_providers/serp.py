# src/glue/tools/search_providers/serp.py

"""SERP API Search Provider Implementation"""

import aiohttp
from typing import Dict, List, Any, Optional
from .base import SearchProvider, SearchResult

class SerpSearchProvider(SearchProvider):
    """SERP API search provider implementation"""
    
    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://serpapi.com/search",
        **config
    ):
        super().__init__(api_key, **config)
        self.endpoint = endpoint
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize aiohttp session"""
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def cleanup(self) -> None:
        """Clean up aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        Perform search using SERP API
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional SERP API parameters
                engine: Search engine to use (google, bing, etc.)
                location: Location for search results
                gl: Country code for search
                hl: Language code for search
                
        Returns:
            List of SearchResult objects
        """
        # Ensure session is initialized
        await self.initialize()
        
        # Build search parameters
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": kwargs.get("engine", "google"),
            "num": max_results,
            **{k: v for k, v in kwargs.items() if k not in ["engine"]}
        }
        
        try:
            # Make request
            async with self._session.get(self.endpoint, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Extract organic results
                results = []
                for item in data.get("organic_results", [])[:max_results]:
                    result = SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        extra={
                            "position": item.get("position"),
                            "displayed_link": item.get("displayed_link"),
                            "cached_page_link": item.get("cached_page_link"),
                            "related_pages_link": item.get("related_pages_link"),
                            "rich_snippet": item.get("rich_snippet")
                        }
                    )
                    results.append(result)
                
                return results
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"SERP API request failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"SERP API search failed: {str(e)}")
    
    def __str__(self) -> str:
        return f"SerpSearchProvider(endpoint={self.endpoint})"
