"""Example demonstrating natural language tool usage with SmolAgents

This example shows how models can use tools naturally without XML tags,
and how SmolAgents parses their intentions into tool executions.
"""

import asyncio
from glue.core.types import AdhesiveType
from glue.core.model import Model
from glue.core.team import Team
from glue.tools.web_search import WebSearchTool
from glue.tools.file_handler import FileHandlerTool
from glue.providers.openrouter import OpenRouterProvider

async def main():
    # Create a team with tools
    team = Team("researchers")
    web_search = WebSearchTool()
    web_search.name = "web_search"
    file_handler = FileHandlerTool()
    file_handler.name = "file_handler"
    
    await team.add_tool(web_search)
    await team.add_tool(file_handler)
    
    # Create a model that can use tools
    model = OpenRouterProvider(
        name="researcher",
        team=team,  # Pass team instance instead of string
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO, AdhesiveType.TAPE},
        api_key="your-api-key"  # Replace with actual key
    )
    
    # Set model's role
    model.set_role("Research topics and save findings")
    
    # Add model's tools from team
    model._tools = team.tools
    
    # Example 1: Web search with GLUE
    response = await model.process(
        "Can you research the latest developments in quantum computing " +
        "and share the findings with the team?"
    )
    print("\nExample 1 - Web Search with GLUE:")
    print(response)
    
    # Example 2: Save results with VELCRO
    response = await model.process(
        "Save those quantum computing findings to a file for my reference"
    )
    print("\nExample 2 - File Handler with VELCRO:")
    print(response)
    
    # Example 3: Quick web check with TAPE
    response = await model.process(
        "Quickly check if there are any quantum computing conferences this month"
    )
    print("\nExample 3 - Web Search with TAPE:")
    print(response)
    
    # Example 4: Dynamic tool creation
    response = await model.process(
        "I need a tool that can format research papers in APA style. " +
        "Can you create one and format our quantum computing findings?"
    )
    print("\nExample 4 - Dynamic Tool Creation:")
    print(response)
    
    # Example 5: MCP tool usage
    response = await model.process(
        "What's the weather like in quantum research hubs? " +
        "Let's check Boston, Copenhagen, and Tokyo."
    )
    print("\nExample 5 - MCP Weather Tool:")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
