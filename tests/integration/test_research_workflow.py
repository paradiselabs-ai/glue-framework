"""Test end-to-end research workflow with dynamic tools"""

import pytest
import pytest_asyncio
from pathlib import Path

from glue.core.app import GlueApp
from glue.dsl.parser import parse_glue_file
from glue.dsl.executor import execute_glue_app

@pytest_asyncio.fixture
async def app():
    """Get running research assistant app instance"""
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    yield app
    await app.cleanup()

@pytest.mark.asyncio
async def test_research_with_dynamic_tools():
    """Test research workflow with dynamic tool creation"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # 1. Request research with tool creation
        result = await app.process_prompt(
            """Research quantum computing advancements in 2024. While doing this:
            1. Create a tool to extract and format academic citations
            2. Create a tool to analyze research trends
            3. Create an MCP server to track paper statistics"""
        )
        
        # Verify tools were created
        assert "citation" in result.lower()
        assert "trends" in result.lower()
        assert "statistics" in result.lower()
        
        # 2. Use the tools collaboratively
        result = await app.process_prompt(
            "Analyze recent quantum computing papers and create a summary with citations"
        )
        
        # Verify collaborative usage
        assert "citation" in result.lower()
        assert "analysis" in result.lower()
        assert "trends" in result.lower()
        
        # 3. Have docs team pull and use the tools
        result = await app.process_prompt(
            "Have the docs team pull the research and create a formatted report"
        )
        
        # Verify docs team usage
        assert "report" in result.lower()
        assert "citation" in result.lower()
        assert "formatted" in result.lower()
        
        # 4. Enhance existing tools
        result = await app.process_prompt(
            "Enhance the citation tool to also include DOI links"
        )
        
        # Verify enhancement
        assert "enhanced" in result.lower()
        assert "doi" in result.lower()
        
        # 5. Create tool chain
        result = await app.process_prompt(
            """Create a research pipeline that:
            1. Searches for papers
            2. Extracts key findings
            3. Generates citations
            4. Creates visualizations
            5. Compiles a report"""
        )
        
        # Verify pipeline creation
        assert "pipeline" in result.lower() or "chain" in result.lower()
        assert "created" in result.lower()
        
        # 6. Use pipeline for research
        result = await app.process_prompt(
            "Research quantum error correction using the research pipeline"
        )
        
        # Verify pipeline output
        assert "findings" in result.lower()
        assert "visualization" in result.lower()
        assert "report" in result.lower()
        assert "citation" in result.lower()
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_team_tool_sharing():
    """Test tool sharing between teams"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # 1. Research team creates tools
        result = await app.process_prompt(
            """Have the research team:
            1. Create a citation tool
            2. Create a visualization tool
            3. Share them with the docs team"""
        )
        
        # Verify tool creation and sharing
        assert "created" in result.lower()
        assert "shared" in result.lower()
        
        # 2. Docs team uses shared tools
        result = await app.process_prompt(
            "Have the docs team use the shared tools to create a report"
        )
        
        # Verify tool usage
        assert "report" in result.lower()
        assert "citation" in result.lower()
        assert "visualization" in result.lower()
        
        # 3. Docs team enhances tools
        result = await app.process_prompt(
            "Have the docs team enhance the visualization tool with new chart types"
        )
        
        # Verify enhancement
        assert "enhanced" in result.lower()
        assert "chart" in result.lower()
        
        # 4. Research team uses enhanced tools
        result = await app.process_prompt(
            "Have the research team use the enhanced visualization tool"
        )
        
        # Verify enhanced tool usage
        assert "visualization" in result.lower()
        assert "chart" in result.lower()
        
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_natural_research_flow():
    """Test natural research flow with dynamic tools"""
    # Create app instance
    app_path = Path("examples/research_assistant.glue")
    config = parse_glue_file(app_path)
    app = await execute_glue_app(config)
    
    try:
        # Natural research request
        result = await app.process_prompt(
            """Research quantum computing breakthroughs in 2024. 
            Create any tools you need along the way to help analyze and present the findings."""
        )
        
        # Verify natural tool creation and usage
        assert "quantum" in result.lower()
        assert "computing" in result.lower()
        assert "created" in result.lower()
        assert "tool" in result.lower()
        assert "findings" in result.lower()
        
        # Follow-up analysis
        result = await app.process_prompt(
            "Analyze the trends in these breakthroughs and create a visual summary"
        )
        
        # Verify analysis and visualization
        assert "trends" in result.lower()
        assert "visual" in result.lower()
        assert "summary" in result.lower()
        
        # Documentation request
        result = await app.process_prompt(
            "Create a comprehensive report of the findings with proper citations"
        )
        
        # Verify documentation
        assert "report" in result.lower()
        assert "citation" in result.lower()
        assert "findings" in result.lower()
        
    finally:
        await app.cleanup()
