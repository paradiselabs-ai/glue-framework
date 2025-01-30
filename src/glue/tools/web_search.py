"""Web Search Tool Implementation"""

import re
import os
import aiohttp
from typing import Dict, List, Optional, Any, Type, Union
from .base import BaseTool, ToolConfig, ToolPermission
from .search_providers import get_provider, SearchProvider, GenericSearchProvider
from ..core.logger import get_logger
from ..core.tool_binding import ToolBinding
from ..core.types import AdhesiveType

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
    
    def _get_api_key(self, provider: str) -> str:
        """Get API key from environment based on provider name"""
        # Convert provider name to environment variable format (e.g., "serp" -> "SERP_API_KEY")
        env_var = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"No API key found for {provider}. Please set {env_var} in your environment.")
        return api_key

    def __init__(
        self,
        name: str = "web_search",
        description: str = "Performs web searches and returns results",
        provider: str = "serp",
        max_results: int = 5,
        binding_type: Optional[AdhesiveType] = None,
        **provider_config
    ):
        # Get API key from environment
        api_key = self._get_api_key(provider)

        # Initialize base tool
        super().__init__(
            name=name,
            description=description,
            adhesive_type=binding_type or AdhesiveType.VELCRO,
            config=ToolConfig(
                required_permissions=[ToolPermission.NETWORK],
                tool_specific_config={
                    "max_results": max_results,
                    "provider": provider,
                    "provider_config": provider_config,
                    "api_key": api_key
                }
            ),
            tags={"web_search", "network", "research"}
        )
        
        # Set up provider endpoints
        provider_endpoints = {
            "tavily": "https://api.tavily.com/search",
            "serp": "https://serpapi.com/search",
            "bing": "https://api.bing.microsoft.com/v7.0/search",
            "you": "https://api.you.com/search",
        }
        
        # Update provider config with default endpoint if needed
        if provider in provider_endpoints and "endpoint" not in provider_config:
            provider_config["endpoint"] = provider_endpoints[provider]
        
        # Initialize provider and session
        self.provider = get_provider(provider, api_key, **provider_config)
        self.max_results = max_results
        self.logger = get_logger()
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self, *args, **kwargs) -> None:
        """Initialize search provider and session"""
        if not self._session:
            self._session = aiohttp.ClientSession()
            # Pass session to provider
            if hasattr(self.provider, 'set_session'):
                await self.provider.set_session(self._session)
        await self.provider.initialize()
        await super().initialize(*args, **kwargs)

    async def cleanup(self) -> None:
        """Clean up search provider and session"""
        if self._session:
            await self._session.close()
            self._session = None
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

    async def _validate_input(self, *args, **kwargs) -> bool:
        """Validate tool input"""
        input_data = args[0] if args else kwargs.get("input_data", "")
        if not input_data:
            return False
        return True

    def _prepare_query(self, input_data: Any) -> str:
        """Convert input to search query"""
        if isinstance(input_data, str):
            return input_data
        if isinstance(input_data, dict) and 'query' in input_data:
            return input_data['query']
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

    async def _execute(self, *args, **kwargs) -> Union[str, List[Dict[str, str]]]:
        """Execute web search with team resource sharing"""
        try:
            # Get and prepare query
            input_data = args[0] if args else kwargs.get("input_data", "")
            base_query = self._prepare_query(input_data)
            self.logger.debug(f"Base query: {base_query}")
            
            # Try optimized queries
            all_results = []
            queries = self._optimize_query(base_query)
            
            for query in queries:
                try:
                    # Search with current query
                    results = await self.provider.search(
                        query=query,
                        max_results=self.max_results,
                        **kwargs
                    )
                    
                    # Add results
                    all_results.extend([r.to_dict() for r in results])
                    if len(all_results) >= self.max_results:
                        break
                        
                except Exception as e:
                    self.logger.error(f"Search failed for query '{query}': {str(e)}")
                    continue
            
            # Handle no results
            if not all_results:
                raise RuntimeError("No search results found")
            
            # Format and store results
            final_results = all_results[:self.max_results]
            formatted_results = self._format_results_as_markdown(final_results, base_query)
            
            # Share with team if using GLUE adhesive
            if self.adhesive_type == AdhesiveType.GLUE:
                self.binding.store_resource("search_results", formatted_results)
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {str(e)}")
            raise RuntimeError(f"Search failed: {str(e)}")

    def __str__(self) -> str:
        """String representation"""
        return f"{self.name}: {self.description} (Binding: {self.binding.type.name})"
