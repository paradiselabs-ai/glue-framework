"""Web Search Tool Implementation"""

import re
from typing import Dict, List, Optional, Any, Type, Union
from .base import BaseTool, ToolConfig, ToolPermission
from .search_providers import get_provider, SearchProvider, GenericSearchProvider
from ..core.logger import get_logger
from ..core.resource import ResourceState

class WebSearchTool(BaseTool):
    """
    Tool for performing web searches with resource capabilities.
    
    Features:
    - Web search integration
    - Query optimization
    - Result formatting
    - Resource state tracking
    - Field interactions
    """
    
    def __init__(
        self,
        api_key: str,
        name: str = "web_search",
        description: str = "Performs web searches and returns results",
        provider: str = "serp",
        max_results: int = 5,
        **provider_config
    ):
        super().__init__(
            name=name,
            description=description,
            config=ToolConfig(
                required_permissions=[
                    ToolPermission.NETWORK,
                    ToolPermission.READ
                ],
                timeout=10.0,
                cache_results=True
            )
        )
        
        # Get provider class and config
        provider_class = get_provider(provider, **provider_config)
        
        # If endpoint not in config but provider has default endpoint, add it
        if issubclass(provider_class, GenericSearchProvider):
            provider_endpoints = {
                "tavily": "https://api.tavily.com/search",
                "serp": "https://serpapi.com/search",
                "bing": "https://api.bing.microsoft.com/v7.0/search",
                "you": "https://api.you.com/search",
            }
            if provider in provider_endpoints and "endpoint" not in provider_config:
                provider_config["endpoint"] = provider_endpoints[provider]
        
        # Initialize provider
        self.provider = provider_class(
            api_key=api_key,
            **provider_config
        )
        self.max_results = max_results
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize search provider"""
        await self.provider.initialize()
        await super().initialize()

    async def cleanup(self) -> None:
        """Clean up search provider"""
        await self.provider.cleanup()
        await super().cleanup()

    def _optimize_query(self, query: str) -> List[str]:
        """Optimize search query for better results"""
        # Extract key concepts
        concepts = []
        
        # Look for field/domain indicators
        domain_match = re.search(r'in\s+(\w+(?:\s+\w+)*)', query)
        if domain_match:
            concepts.append(domain_match.group(1))
        
        # Look for temporal indicators
        if any(word in query.lower() for word in ['latest', 'recent', 'new', 'current']):
            concepts.append('2023')  # Current year
        
        # Extract noun phrases (simple approach)
        words = query.split()
        for i in range(len(words)-1):
            if not words[i].lower() in ['the', 'a', 'an', 'in', 'on', 'at', 'for']:
                concepts.append(f"{words[i]} {words[i+1]}")
        
        # Generate optimized queries
        queries = []
        base_concepts = [c for c in concepts if len(c.split()) > 1]
        if not base_concepts:
            base_concepts = [query]
        
        # Use base query and concepts directly
        queries.append(query)  # Original query first
        queries.extend(base_concepts)  # Then key concepts
        
        return queries[:2]  # Limit to original query + 1 concept

    async def prepare_input(self, input_data: Any) -> str:
        """Prepare input for search"""
        # Check for shared query from attracted resources
        if self._attracted_to:
            for resource in self._attracted_to:
                if hasattr(resource, "query"):
                    return resource.query
        
        # If input is a string, use it directly
        if isinstance(input_data, str):
            return input_data
        
        # If input is a dict with a 'query' field, use that
        if isinstance(input_data, dict) and 'query' in input_data:
            return input_data['query']
        
        # Otherwise, convert to string
        return str(input_data)

    def _format_results_as_markdown(self, results: List[Dict[str, Any]], query: str) -> str:
        """Format search results as a markdown document"""
        lines = [
            f"# Research Results: {query}\n",
            "## Summary of Findings\n"
        ]
        
        for i, result in enumerate(results, 1):
            # Get URL from either 'url' (SearchResult) or 'link' (raw API result)
            url = result.get('url') or result.get('link', 'No link available')
            title = result.get('title', 'Untitled')
            snippet = result.get('snippet', 'No description available')
            
            # Log result details for debugging
            self.logger.debug(f"Result {i}:")
            self.logger.debug(f"  Title: {title}")
            self.logger.debug(f"  URL: {url}")
            self.logger.debug(f"  Snippet: {snippet}")
            
            # Format as markdown with reference-style links
            lines.extend([
                f"### {i}. {title}\n",
                f"{snippet}\n",
                f"[Source][{i}]\n",  # Reference-style link
                f"[{i}]: {url}\n"    # Link definition at end
            ])
        
        return "\n".join(lines)

    async def _execute(self, input_data: Any, **kwargs) -> Union[str, List[Dict[str, str]]]:
        """Execute web search with resource state tracking"""
        try:
            # Get base query from input
            base_query = await self.prepare_input(input_data)
            self.logger.debug(f"Base query: {base_query}")
            
            # Generate optimized queries
            queries = self._optimize_query(base_query)
            self.logger.debug(f"Optimized queries: {queries}")
            
            # Track all results
            all_results = []
            
            # Try each query until we get good results
            for query in queries:
                # Share query with attracted resources
                if self._attracted_to:
                    for resource in self._attracted_to:
                        if hasattr(resource, "query"):
                            resource.query = query
                
                # Perform search
                try:
                    self.logger.debug(f"Searching with query: {query}")
                    results = await self.provider.search(
                        query=query,
                        max_results=self.max_results,
                        **kwargs
                    )
                    
                    # Convert to dictionary format
                    results_dict = [result.to_dict() for result in results]
                    self.logger.debug(f"Got {len(results_dict)} results")
                    
                    # Add results
                    all_results.extend(results_dict)
                    
                    # If we have enough relevant results, stop
                    if len(all_results) >= self.max_results:
                        break
                except Exception as e:
                    self.logger.error(f"Search failed for query '{query}': {str(e)}")
                    continue
            
            if not all_results:
                raise RuntimeError("No search results found for any query")
            
            # Take top results
            final_results = all_results[:self.max_results]
            
            # Format results as markdown
            formatted_results = self._format_results_as_markdown(final_results, base_query)
            
            # Share results with attracted resources
            if self._attracted_to:
                for resource in self._attracted_to:
                    if hasattr(resource, "search_results"):
                        resource.search_results = formatted_results
            
            # Return formatted results
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {str(e)}")
            raise RuntimeError(f"Search failed: {str(e)}")

    def __str__(self) -> str:
        """String representation"""
        status = super().__str__()
        return f"{status} | Provider: {self.provider}"
