# examples/doc_generator.py

"""Example: Documentation Generator using GLUE Expression Language"""

from src.glue.expressions import glue_app, field, magnetize
from src.glue.tools.web_search import WebSearchTool
from src.glue.tools.code_interpreter import CodeInterpreterTool
from src.glue.tools.file_handler import FileHandlerTool

@glue_app("doc_generator")
async def generate_docs(topic: str, output_dir: str = "docs"):
    """Generate documentation with examples"""
    async with field("documentation"):
        # Create tools with specific configurations
        tools = magnetize({
            "search": WebSearchTool(
                api_key="your-api-key",
                name="search",
                description="Example finder",
                strength="strong"
            ),
            "interpreter": CodeInterpreterTool(
                name="interpreter",
                description="Code generator",
                strength="medium",
                supported_languages=["python", "markdown"]
            ),
            "file": FileHandlerTool(
                name="file",
                description="File handler",
                strength="medium"
            )
        })
        
        # Create documentation chain
        search_chain = (
            tools["search"]  # Search for examples
            >> {"memory": tools["interpreter"]}  # Store in interpreter's memory
        )
        
        generate_chain = (
            tools["interpreter"]  # Generate documentation
            >> tools["file"]      # Save documentation
        )
        
        # Execute documentation generation
        examples = await search_chain({
            "query": f"python {topic} example code",
            "max_results": 5
        })
        
        # Generate markdown documentation
        doc_template = f"""
# {topic} Documentation

## Overview
Auto-generated documentation for {topic}.

## Examples
{examples}

## Generated Code
```python
{examples['code'] if isinstance(examples, dict) else 'No code available'}
```
"""
        
        result = await generate_chain({
            "code": doc_template,
            "language": "markdown",
            "output_file": f"{output_dir}/{topic.lower().replace(' ', '_')}.md"
        })
        
        return result

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        result = await generate_docs(
            topic="Python Context Managers",
            output_dir="generated_docs"
        )
        print(f"Documentation generation completed: {result}")
    
    asyncio.run(main())
