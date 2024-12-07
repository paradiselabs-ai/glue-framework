# src/glue/tools/search_providers/base.py

"""Base Search Provider Implementation"""

import aiohttp
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class SearchResult:
    """Search Result Data"""
    title: str
    url: str
    snippet: str
    extra: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            **(self.extra or {})
        }

class SearchProvider(ABC):
    """Base class for search providers"""
    
    def __init__(self, api_key: str, endpoint: str = None, **config):
        self.api_key = api_key
        self.endpoint = endpoint
        self.config = config
        self._session = None
    
    async def initialize(self) -> None:
        """Initialize provider resources"""
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def cleanup(self) -> None:
        """Clean up provider resources"""
        if self._session:
            await self._session.close()
            self._session = None
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        """Execute search and return results"""
        pass

class GenericSearchProvider(SearchProvider):
    """Generic search provider that works with any REST API"""
    
    def __init__(self, api_key: str, endpoint: str, **config):
        super().__init__(api_key=api_key, endpoint=endpoint, **config)
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    async def _try_request(self, method: str, query: str, max_results: int, **kwargs) -> Optional[Dict]:
        """Try a request with a specific method"""
        try:
            # Prepare request data
            params = None
            json_data = None
            
            if method == "GET":
                params = {
                    "q": query,
                    "max_results": max_results,
                    **kwargs
                }
            else:
                json_data = {
                    "query": query,
                    "max_results": max_results,
                    **kwargs
                }
            
            # Make request
            async with self._session.request(
                method,
                self.endpoint,
                headers=self.headers,
                params=params,
                json=json_data
            ) as response:
                if response.status == 405:  # Method Not Allowed
                    return None
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            if e.status == 405:  # Method Not Allowed
                return None
            raise
        except Exception:
            return None
    
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        """Execute search using the configured API"""
        if not self._session:
            await self.initialize()
        
        # Try different request methods
        data = None
        last_error = None
        
        for method in ["GET", "POST", "PUT"]:
            try:
                data = await self._try_request(method, query, max_results, **kwargs)
                if data is not None:
                    break
            except Exception as e:
                last_error = e
        
        if data is None:
            if last_error:
                raise last_error
            raise RuntimeError("All request methods failed")
        
        # Extract results - try common response formats
        results_data = None
        for path in [["results"], ["data", "results"], ["items"], ["hits"], ["response", "results"]]:
            current = data
            valid = True
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    valid = False
                    break
            if valid and isinstance(current, list):
                results_data = current
                break
        
        if not results_data:
            # If no standard path found, try first list in response
            for value in data.values():
                if isinstance(value, list):
                    results_data = value
                    break
        
        if not results_data:
            # If still no results found, use entire response
            results_data = [data]
        
        # Convert to SearchResult objects
        results = []
        for item in results_data[:max_results]:
            if isinstance(item, dict):
                # Try common field names for each attribute
                title = None
                for key in ["title", "name", "heading", "subject"]:
                    if key in item:
                        title = str(item[key])
                        break
                
                url = None
                for key in ["url", "link", "href"]:
                    if key in item:
                        url = str(item[key])
                        break
                
                snippet = None
                for key in ["snippet", "description", "content", "text", "summary"]:
                    if key in item:
                        snippet = str(item[key])
                        break
                
                if title and url and snippet:
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        extra=item
                    ))
        
        return results
