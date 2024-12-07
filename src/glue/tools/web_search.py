# src/glue/tools/web_search.py

"""Web Search Tool Implementation"""

import re
from typing import Dict, List, Optional, Any, Type, Union
from .base import ToolConfig, ToolPermission
from .magnetic import MagneticTool
from .search_providers import get_provider, SearchProvider, GenericSearchProvider

class WebSearchTool(MagneticTool):
    """Tool for performing web searches with magnetic capabilities"""
    
    def __init__(
        self,
        api_key: str,
        name: str = "web_search",
        description: str = "Performs web searches and returns results",
        provider: str = "serp",
        max_results: int = 5,
        magnetic: bool = True,
        sticky: bool = False,
        **provider_config
    ):
        super().__init__(
            name=name,
            description=description,
            magnetic=magnetic,
            sticky=sticky,
            shared_resources=["query", "search_results", "last_search"],
            config=ToolConfig(
                required_permissions=[
                    ToolPermission.NETWORK,
                    ToolPermission.READ,
                    ToolPermission.MAGNETIC
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
        
        # Look for type indicators
        if any(word in query.lower() for word in ['research', 'paper', 'study', 'development']):
            concepts.append('research')
        
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
        
        for base in base_concepts:
            # Academic focus
            queries.append(f"latest research {base} academic")
            queries.append(f"recent developments {base} scientific")
            
            # Field specific
            if 'physics' in query.lower():
                queries.append(f"{base} physics research paper")
            if 'theory' in query.lower():
                queries.append(f"{base} theoretical developments")
        
        return queries[:3]  # Limit to top 3 queries

    async def prepare_input(self, input_data: Any) -> str:
        """Prepare input for search"""
        # First check if we have a query shared magnetically
        if self.magnetic:
            shared_query = self.get_shared_resource("query")
            if shared_query:
                return shared_query
        
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
            lines.extend([
                f"### {i}. {result.get('title', 'Untitled')}\n",
                f"**Source**: {result.get('link', 'No link available')}\n",
                f"{result.get('snippet', 'No description available')}\n"
            ])
        
        return "\n".join(lines)

    async def execute(self, input_data: Any, **kwargs) -> Union[str, List[Dict[str, str]]]:
        """Execute web search with magnetic sharing"""
        try:
            # Get base query from input
            base_query = await self.prepare_input(input_data)
            
            # Generate optimized queries
            queries = self._optimize_query(base_query)
            
            # Track all results
            all_results = []
            
            # Try each query until we get good results
            for query in queries:
                # Share query magnetically
                if self.magnetic:
                    await self.share_resource("query", query)
                
                # Perform search
                results = await self.provider.search(
                    query=query,
                    max_results=self.max_results,
                    **kwargs
                )
                
                # Convert to dictionary format
                results_dict = [result.to_dict() for result in results]
                
                # Add results
                all_results.extend(results_dict)
                
                # If we have enough relevant results, stop
                if len(all_results) >= self.max_results:
                    break
            
            # Take top results
            final_results = all_results[:self.max_results]
            
            # Format results as markdown
            formatted_results = self._format_results_as_markdown(final_results, base_query)
            
            # Share results magnetically
            if self.magnetic:
                await self.share_resource("search_results", formatted_results)
                await self.share_resource("last_search", {
                    "original_query": base_query,
                    "optimized_queries": queries,
                    "results": final_results
                })
            
            # Return formatted results instead of raw results
            return formatted_results
            
        except Exception as e:
            raise RuntimeError(f"Search failed: {str(e)}")

    async def _on_resource_shared(self, source: 'MagneticTool', resource_name: str, data: Any) -> None:
        """Handle shared resources from other tools"""
        # If we receive file content that looks like a search query, use it
        if resource_name == "file_content" and isinstance(data, str):
            # Simple heuristic: if it ends with a question mark or has search keywords
            search_keywords = ["what", "how", "who", "where", "when", "why", "find", "search"]
            if (data.strip().endswith("?") or 
                any(keyword in data.lower() for keyword in search_keywords)):
                await self.share_resource("query", data.strip())

    def __str__(self) -> str:
        status = []
        if self.magnetic:
            status.append("Magnetic")
            if self.shared_resources:
                status.append(f"Shares: {', '.join(self.shared_resources)}")
            if self.sticky:
                status.append("Sticky")
        return (
            f"{self.name}: {self.description} "
            f"(Provider: {self.provider}"
            f"{' - ' + ', '.join(status) if status else ''})"
        )
