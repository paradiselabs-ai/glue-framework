# src/glue/tools/search_providers/__init__.py

"""Search Provider Registry"""

from typing import Dict, Type
from .base import SearchProvider, GenericSearchProvider
from .serp import SerpSearchProvider

# Provider registry
SEARCH_PROVIDERS: Dict[str, Type[SearchProvider]] = {
    'serp': SerpSearchProvider,
    'serpapi': SerpSearchProvider
}

def register_provider(name: str, provider_class: Type[SearchProvider]) -> None:
    """Register a search provider"""
    SEARCH_PROVIDERS[name] = provider_class

def get_provider(name: str, api_key: str, **config) -> SearchProvider:
    """Get a search provider instance by name or create generic provider"""
    provider_class = None
    
    # If endpoint is provided, use generic provider
    if "endpoint" in config:
        provider_class = GenericSearchProvider
    
    # Check if it's a registered provider
    elif name in SEARCH_PROVIDERS:
        provider_class = SEARCH_PROVIDERS[name]
    
    # If neither, use generic provider with default endpoint
    else:
        provider_endpoints = {
            "tavily": "https://api.tavily.com/search",
            "serp": "https://serpapi.com/search",
            "bing": "https://api.bing.microsoft.com/v7.0/search",
            "you": "https://api.you.com/search",
        }
        
        if name in provider_endpoints:
            config["endpoint"] = provider_endpoints[name]
            provider_class = GenericSearchProvider
        else:
            # If unknown provider and no endpoint, raise error
            raise ValueError(
                f"Unknown search provider: {name}. Either:\n"
                f"1. Use a known provider: {', '.join(provider_endpoints.keys())}\n"
                "2. Provide an endpoint in your GLUE file:\n"
                "   web_search {\n"
                "       your_provider\n"
                "       endpoint = 'https://api.your-provider.com/search'\n"
                "       os.your_provider_api_key\n"
                "   }"
            )
    
    # Create and return provider instance
    return provider_class(api_key=api_key, **config)

# Example GLUE file usage:
"""
# Using known provider
web_search {
    tavily
    os.tavily_api_key
}

# Using custom API
web_search {
    your_provider
    endpoint = "https://api.your-provider.com/search"
    os.your_provider_api_key
}
"""

__all__ = [
    'SearchProvider',
    'GenericSearchProvider',
    'register_provider',
    'get_provider',
    'SEARCH_PROVIDERS',
    'SerpSearchProvider'
]
