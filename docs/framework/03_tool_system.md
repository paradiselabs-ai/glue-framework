# GLUE Tool System

## Overview

The GLUE Tool System is designed to be flexible and extensible, allowing models to interact with external systems and perform various tasks. Tools can be used with different adhesive bindings to control their persistence and sharing behavior.

## Built-in Tools

### 1. Web Search

```glue
tool web_search {
    provider = serp  // Uses SERP_API_KEY from environment
}
```

Features:

- Multiple search providers (SERP, Tavily)
- Query optimization
- Result formatting
- Automatic API key management

### 2. File Handler

```glue
tool file_handler {}
```

Features:

- File reading/writing
- Directory operations
- Path management
- Workspace isolation

### 3. Code Interpreter

```glue
tool code_interpreter {
    config {
        languages = ["python", "javascript"]
        sandbox = true
    }
}
```

Features:

- Multi-language support
- Sandboxed execution
- Context persistence
- Package management

## Using Tools

### 1. Tool Declaration

Tools are declared at the application level and then assigned to teams:

```glue
// Declare tools
tool web_search {
    provider = serp
}

tool code_interpreter {}

// Assign to team
magnetize {
    research {
        tools = [web_search, code_interpreter]
    }
}
```

### 2. Adhesive Bindings

Models use tools with different adhesive types:

```python
# Python code example:
# GLUE binding - results shared with team
result = await model.use_tool("web_search", AdhesiveType.GLUE, "quantum computing")

# VELCRO binding - results persist for session
code = await model.use_tool("code_interpreter", AdhesiveType.VELCRO, "print('Hello')")

# TAPE binding - one-time use
fact = await model.use_tool("web_search", AdhesiveType.TAPE, "verify this fact")
```

```glue
// GLUE expression language example:
model researcher {
    adhesives = [glue]     // Use GLUE for persistent results
}

model verifier {
    adhesives = [tape]     // Use TAPE for one-time verification
}
```

### 3. Result Handling

Tool results are handled based on the adhesive type:

- GLUE: Results automatically shared with team
- VELCRO: Results stored in model's session
- TAPE: Results returned but not stored

## Creating Custom Tools

### 1. Basic Tool Structure

```python
from glue.tools.simple_base import SimpleBaseTool, ToolConfig, ToolPermission

class CustomTool(SimpleBaseTool):
    def __init__(
        self,
        name: str = "custom_tool",
        description: str = "Custom tool description",
        **config
    ):
        super().__init__(
            name=name,
            description=description,
            config=ToolConfig(
                required_permissions=[
                    ToolPermission.READ,
                    ToolPermission.WRITE
                ],
                timeout=30.0
            )
        )
        self.config = config

    async def _execute(self, *args, **kwargs) -> Any:
        """Tool implementation goes here"""
        # Your code here
        return result
```

### 2. Adding API Integration

```python
class ApiTool(SimpleBaseTool):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(...)
        # Get API key from environment if not provided
        self.api_key = api_key or os.getenv("API_KEY")
        if not self.api_key:
            raise ValueError("API key required")

    async def initialize(self):
        """Set up API client"""
        self._client = ApiClient(self.api_key)
        await super().initialize()

    async def cleanup(self):
        """Clean up resources"""
        await self._client.close()
        await super().cleanup()
```

### 3. Registering Custom Tools

```python
# Python implementation example:
from glue.tools import register_tool

@register_tool
class MyTool(SimpleBaseTool):
    """Tool will be available in GLUE applications"""
    pass
```

```glue
// GLUE usage example:
tool my_tool {
    // Tool configuration here
}
```

## Best Practices

### 1. Tool Design

- Keep tools focused on a single responsibility
- Handle errors gracefully
- Provide clear feedback
- Document requirements and usage

### 2. Resource Management

- Clean up resources in cleanup()
- Use async context managers
- Handle timeouts appropriately
- Cache results when beneficial

### 3. Security

- Validate inputs
- Use appropriate permissions
- Sanitize outputs
- Handle sensitive data carefully

### 4. Performance

- Use async operations
- Implement caching
- Batch operations when possible
- Monitor resource usage

## Example: Custom Search Tool

```python
from glue.tools.simple_base import SimpleBaseTool
from typing import Optional, Dict, Any

class CustomSearchTool(SimpleBaseTool):
    """Custom search tool example"""
    
    def __init__(
        self,
        name: str = "custom_search",
        api_key: Optional[str] = None
    ):
        super().__init__(
            name=name,
            description="Custom search implementation",
            config=ToolConfig(
                required_permissions=[ToolPermission.NETWORK],
                timeout=10.0
            )
        )
        self.api_key = api_key or os.getenv("CUSTOM_SEARCH_KEY")
        self._session = None

    async def initialize(self):
        """Initialize search client"""
        self._session = aiohttp.ClientSession()
        await super().initialize()

    async def cleanup(self):
        """Clean up resources"""
        if self._session:
            await self._session.close()
        await super().cleanup()

    async def _execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """Execute search"""
        try:
            async with self._session.get(
                "https://api.search.com/v1/search",
                params={"q": query, "key": self.api_key}
            ) as response:
                data = await response.json()
                return self._format_results(data)
        except Exception as e:
            raise RuntimeError(f"Search failed: {str(e)}")

    def _format_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format search results"""
        return {
            "results": data.get("items", []),
            "total": data.get("total", 0)
        }
```

## Next Steps

- [Example Applications](04_examples.md)
- [Best Practices](05_best_practices.md)
- [API Reference](06_api_reference.md)
