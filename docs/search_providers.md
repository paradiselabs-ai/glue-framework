# Search Providers in GLUE

GLUE makes it easy to use any search API in your applications. Just specify the provider name and API key - GLUE handles the rest!

## Using Search Providers

### Known Providers

Just specify the provider name and API key:

```glue
web_search {
    tavily
    os.tavily_api_key
}
```

GLUE supports these providers out of the box:
- Tavily (`tavily`)
- SERP API (`serp`)
- Bing Search (`bing`)
- You.com (`you`)

### Custom Search APIs

Have your own search API? Just add the endpoint:

```glue
web_search {
    your_provider
    endpoint = "https://api.your-provider.com/search"
    os.your_provider_api_key
}
```

### Example: Google Custom Search

Since Google Custom Search requires a custom engine ID, use it as a custom provider:

```glue
web_search {
    google_pse
    endpoint = "https://www.googleapis.com/customsearch/v1"
    os.google_api_key
    engine_id = "your_engine_id"  # Your custom search engine ID
}
```

## Search Results

All search providers return results in a standard format:
- Title
- URL
- Snippet
- Extra data (provider-specific)

## Using with Chains

Want to do more with search results? Use chains!

### Save Results to File

```glue
web_search {
    tavily
    os.tavily_api_key
}

file_writer {
    path = "results.json"
}

researcher {
    openrouter
    os.api_key
    double_side_tape = { web_search >> file_writer }
}
```

### Analyze Results

```glue
web_search {
    tavily
    os.tavily_api_key
}

analyzer {
    openrouter
    os.api_key
    role = "Extract key insights from search results"
}

researcher {
    openrouter
    os.api_key
    double_side_tape = { web_search >> analyzer }
}
```

## Best Practices

1. **API Keys**
   - Store API keys in environment variables
   - Use the `os.key_name` syntax in GLUE files

2. **Error Handling**
   - GLUE automatically handles API errors
   - Provides meaningful error messages

3. **Rate Limiting**
   - GLUE respects API rate limits
   - Implements exponential backoff

4. **Results**
   - All results are returned in a standard format
   - Results are always shown to the user
   - Use chains for additional processing
