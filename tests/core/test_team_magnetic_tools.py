"""Test team communication and magnetic fields with SmolAgents tools"""

import pytest
from glue.providers.smolagents import SmolAgentsProvider
from glue.core.types import AdhesiveType
from glue.core.team import Team
from glue.magnetic.field import MagneticField

@pytest.mark.asyncio
async def test_team_magnetic_flow():
    """Test magnetic flow between teams using SmolAgents tools"""
    # Create magnetic field
    field = MagneticField(name="research_flow")
    
    # Create teams
    research_team = Team(name="research_team")
    analysis_team = Team(name="analysis_team")
    
    # Create providers with different adhesives
    researcher = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    analyst = SmolAgentsProvider(
        name="analyst",
        team="analysis_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        api_key="test-key"
    )
    
    # Set up magnetic flow
    await field.set_team_flow(
        source_team="research_team",
        target_team="analysis_team",
        operator="->"  # Research pushes to analysis
    )
    
    # Create dynamic tools for each team
    async def collect_research(topic: str) -> str:
        return f"Research findings about {topic}: Important discoveries"
        
    async def analyze_findings(data: str) -> str:
        return f"Analysis of '{data}': Key insights identified"
    
    # Create tools dynamically
    research_tool = await researcher.create_tool(
        name="research_collector",
        description="Collect research findings",
        function=collect_research
    )
    
    analysis_tool = await analyst.create_tool(
        name="findings_analyzer",
        description="Analyze research findings",
        function=analyze_findings
    )
    
    # Test magnetic flow
    # 1. Researcher collects data with GLUE adhesive
    research_result = await researcher.use_tool(
        tool_name="research_collector",
        adhesive=AdhesiveType.GLUE,
        input_data="quantum computing"
    )
    
    # Verify research results
    assert "Research findings" in research_result.result
    assert "research_collector" in research_team.shared_results
    
    # Share results through magnetic flow
    await field.share_team_results(
        source_team="research_team",
        target_team="analysis_team",
        results={"research": research_result.result}
    )
    
    # 2. Analyst analyzes data with both adhesives
    # First with GLUE to share back
    glue_analysis = await analyst.use_tool(
        tool_name="findings_analyzer",
        adhesive=AdhesiveType.GLUE,
        input_data=research_result.result
    )
    
    # Then with VELCRO to keep locally
    velcro_analysis = await analyst.use_tool(
        tool_name="findings_analyzer",
        adhesive=AdhesiveType.VELCRO,
        input_data=research_result.result
    )
    
    # Verify analysis results
    assert "Analysis of" in glue_analysis.result
    assert "findings_analyzer" in analysis_team.shared_results
    assert "findings_analyzer" in analyst._session_results
    
    # Verify magnetic field rules
    flows = field.get_team_flows("research_team")
    assert "analysis_team" in flows
    assert flows["analysis_team"] == "->"

@pytest.mark.asyncio
async def test_team_repulsion():
    """Test team repulsion with SmolAgents tools"""
    # Create magnetic field
    field = MagneticField(name="isolated_research")
    
    # Create teams
    research_team = Team(name="research_team")
    external_team = Team(name="external_team")
    
    # Create providers
    researcher = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    external = SmolAgentsProvider(
        name="external",
        team="external_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    # Set up repulsion
    await field.set_team_flow(
        source_team="research_team",
        target_team="external_team",
        operator="<>"  # Teams cannot interact
    )
    
    # Create dynamic tools
    async def research_data(topic: str) -> str:
        return f"Confidential research on {topic}"
    
    research_tool = await researcher.create_tool(
        name="confidential_research",
        description="Conduct confidential research",
        function=research_data
    )
    
    # Test repulsion
    # 1. Researcher creates confidential data
    research_result = await researcher.use_tool(
        tool_name="confidential_research",
        adhesive=AdhesiveType.GLUE,
        input_data="proprietary technology"
    )
    
    # Verify research results are in research team
    assert "Confidential research" in research_result.result
    assert "confidential_research" in research_team.shared_results
    
    # 2. Attempt to share with external team (should fail)
    with pytest.raises(ValueError):
        await field.share_team_results(
            source_team="research_team",
            target_team="external_team",
            results={"research": research_result.result}
        )
    
    # Verify external team cannot access results
    flows = field.get_team_flows("research_team")
    assert "external_team" not in flows

@pytest.mark.asyncio
async def test_pull_flow():
    """Test pull-based flow between teams"""
    # Create magnetic field
    field = MagneticField(name="pull_research")
    
    # Create teams
    research_team = Team(name="research_team")
    docs_team = Team(name="docs_team", is_pull_team=True)
    
    # Create providers
    researcher = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    writer = SmolAgentsProvider(
        name="writer",
        team="docs_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    # Set up pull flow
    await field.set_team_flow(
        source_team="docs_team",
        target_team="research_team",
        operator="<-"  # Docs pulls from research
    )
    
    # Create dynamic tools
    async def research_topic(topic: str) -> str:
        return f"Research on {topic}: Detailed findings"
        
    async def write_doc(content: str) -> str:
        return f"Documentation:\n{content}\n\nFormatted for clarity"
    
    research_tool = await researcher.create_tool(
        name="topic_research",
        description="Research specific topics",
        function=research_topic
    )
    
    doc_tool = await writer.create_tool(
        name="doc_writer",
        description="Write documentation",
        function=write_doc
    )
    
    # Test pull flow
    # 1. Researcher creates content
    research_result = await researcher.use_tool(
        tool_name="topic_research",
        adhesive=AdhesiveType.GLUE,
        input_data="advanced algorithms"
    )
    
    # Verify research results
    assert "Research on" in research_result.result
    assert "topic_research" in research_team.shared_results
    
    # 2. Writer pulls and documents
    # First pull the research
    pulled_results = await field.process_team_flow(
        source_team="research_team",
        target_team="docs_team",
        content=research_result.result,
        flow_type="<-"
    )
    
    # Then create documentation
    doc_result = await writer.use_tool(
        tool_name="doc_writer",
        adhesive=AdhesiveType.GLUE,
        input_data=pulled_results
    )
    
    # Verify documentation results
    assert "Documentation:" in doc_result.result
    assert "doc_writer" in docs_team.shared_results
    
    # Verify pull flow is working
    flows = field.get_team_flows("docs_team")
    assert "research_team" in flows
