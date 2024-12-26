"""Research Assistant PoC demonstrating adhesive-based binding patterns"""

from glue.expressions import glue_app, field, magnet, AttractionStrength
from glue.tools import WebSearchTool, CodeInterpreterTool
from glue.providers import OpenRouterProvider

@glue_app("research_assistant")
async def research_assistant():
    """
    Research Assistant demonstrating different attraction strengths:
    
    1. TAPE: Temporary bindings for quick data flow
       - Search results -> Researcher (temporary data)
       - Researcher -> Generator (one-time generation)
    
    2. VELCRO: Flexible bindings for ongoing work
       - Researcher <-> Assistant (collaborative work)
       - Assistant <-> Tools (flexible tool usage)
    
    3. GLUE: Persistent bindings for core functionality
       - Memory persistence
       - Core model relationships
       - Long-running context
    """
    async with field("research") as f:
        # Create models with different roles
        researcher = OpenRouterProvider(
            name="researcher",
            model="anthropic/claude-3",
            **magnet("researcher", attraction=AttractionStrength.GLUE)
        )
        
        assistant = OpenRouterProvider(
            name="assistant",
            model="openai/gpt-4",
            **magnet("assistant", attraction=AttractionStrength.VELCRO)
        )
        
        fact_checker = OpenRouterProvider(
            name="fact_checker",
            model="anthropic/claude-3-sonnet",
            **magnet("fact_checker", attraction=AttractionStrength.TAPE)
        )
        
        # Create tools
        search = WebSearchTool(
            **magnet("search", attraction=AttractionStrength.TAPE)
        )
        
        code_gen = CodeInterpreterTool(
            **magnet("code_gen", attraction=AttractionStrength.VELCRO)
        )
        
        # Add all resources to field
        for resource in [researcher, assistant, fact_checker, search, code_gen]:
            await f.add_resource(resource)
        
        # Example: Research flow
        
        # 1. TAPE: Quick fact-checking
        # - Search results are temporarily bound to fact_checker
        # - Once verified, binding breaks automatically
        await f.attract(search, fact_checker)
        results = await search.execute("quantum computing basics")
        verified = await fact_checker.process(results)
        # Binding breaks after TTL
        
        # 2. VELCRO: Ongoing research
        # - Assistant and tools have flexible binding
        # - Can reconnect if connection drops
        # - Maintains context but allows independence
        await f.attract(assistant, code_gen)
        await f.attract(assistant, search)
        await assistant.process("Research quantum computing and generate example code")
        # Tools remain bound but flexibly
        
        # 3. GLUE: Core research context
        # - Researcher maintains persistent context
        # - Strong binding ensures context preservation
        # - Critical relationships maintained
        await f.attract(researcher, assistant)
        await researcher.process("Synthesize research and generate report")
        # Binding persists throughout session

if __name__ == "__main__":
    import asyncio
    asyncio.run(research_assistant())
