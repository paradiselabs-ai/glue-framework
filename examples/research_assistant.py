# examples/research_assistant.py

"""Example: Research Assistant using GLUE Expression Language"""

from glue.adhesive import (
    workspace, tool, tape,
    double_side_tape, glue_app
)

@glue_app("research_assistant")
async def research_topic(topic: str, output_file: str = "research.json"):
    """Research a topic and save results"""
    async with workspace("research"):
        # Create tools with tape for development
        tools = tape([
            tool("web_search"),
            tool("file_handler")
        ])
        
        # Create research chain with double-sided tape
        chain = double_side_tape([
            tools["web_search"] >> tools["file_handler"]
        ])
        
        # Execute research
        result = await chain({
            "query": topic,
            "output_file": output_file
        })
        
        return result

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        results = await research_topic(
            topic="GLUE framework development",
            output_file="research_results.json"
        )
        print(f"Research completed: {results}")
    
    asyncio.run(main())
