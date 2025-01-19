"""Example of a research team using GLUE's advanced features"""

import asyncio
from glue.expressions.core import glue_app, team, flow
from glue.providers.openrouter import OpenRouterProvider
from glue.tools.web_search import WebSearch
from glue.tools.file_handler import FileHandler

@glue_app("research_app")
@team("research",
    lead=OpenRouterProvider(
        name="researcher",
        model="anthropic/claude-2",
        system_prompt="You are a skilled researcher who analyzes information and draws insights."
    ),
    tools=[WebSearch()],
    sticky=True,  # Keep research results between runs
    auto_bind=True  # Enable automatic team binding
)
@team("analysis",
    lead=OpenRouterProvider(
        name="analyst",
        model="anthropic/claude-2",
        system_prompt="You are a data analyst who processes and interprets research findings."
    ),
    members=[
        OpenRouterProvider(
            name="assistant",
            model="anthropic/claude-2",
            system_prompt="You help analyze and organize research data."
        )
    ],
    tools=[FileHandler()],
    pull_fallback=True  # Enable pulling if needed
)
@team("docs",
    lead=OpenRouterProvider(
        name="writer",
        model="anthropic/claude-2",
        system_prompt="You are a technical writer who creates clear documentation."
    ),
    tools=[FileHandler()],
    auto_bind=True
)
# Define team interactions
@flow("research", "analysis", "<->")  # Research and analysis collaborate
@flow("analysis", "docs", "->")       # Analysis pushes to docs
@flow("research", "docs", "<>")       # Research and docs don't interact directly
async def research_app(app):
    """
    This example demonstrates:
    1. Team Structure
       - Research team with web search
       - Analysis team with file handling
       - Docs team with file handling
       
    2. Flow Patterns
       - Research <-> Analysis (full collaboration)
       - Analysis -> Docs (push only)
       - Research <> Docs (repulsion)
       
    3. Features
       - Sticky persistence (research)
       - Auto binding (research, docs)
       - Pull fallback (analysis)
       - Implicit team communication
       - Dynamic field strength
       - Memory management
    """
    # Example prompts showing different team interactions
    prompts = [
        # Research team handles initial research
        "Hello! Can you help me research quantum computing?",
        
        # Analysis team processes findings
        "Can you analyze our quantum computing research?",
        
        # Analysis pushes to docs
        "Create a technical document summarizing our findings",
        
        # Docs team can't pull directly from research (repelled)
        "writer, can you get the original research data?",
        
        # But docs can pull from analysis (pull fallback)
        "writer, can you check the analyzed findings?",
        
        # Show memory and field strength
        "What have we learned about quantum computing?",
        
        # Show team communication
        "analyst, can you collaborate with the researcher on this?",
    ]
    
    # Process prompts
    for prompt in prompts:
        print(f"\nUser: {prompt}")
        response = await app.process_prompt(prompt)
        print(f"Assistant: {response}")

if __name__ == "__main__":
    asyncio.run(research_app())
