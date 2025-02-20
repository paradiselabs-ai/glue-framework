"""Integration tests for Magnetic Field with actual components"""

import pytest
from datetime import datetime

from glue.magnetic.field import MagneticField
from glue.core.team import Team, TeamRole
from glue.core.model import Model
from glue.core.pydantic_models import (
    ModelConfig, TeamContext, ToolResult, SmolAgentsTool,
    PrefectTaskConfig
)
from glue.core.types import AdhesiveType
from glue.tools.file_handler import FileHandlerTool
from glue.tools.web_search import WebSearchTool

@pytest.fixture
def team_context():
    return TeamContext()

@pytest.fixture
def source_team(team_context):
    return Team(
        name="source_team",
        context=team_context
    )

@pytest.fixture
def target_team(team_context):
    return Team(
        name="target_team",
        context=team_context
    )

@pytest.fixture
def magnetic_field():
    return MagneticField(name="test_field")

@pytest.mark.asyncio
async def test_research_to_docs_flow(magnetic_field, source_team, target_team):
    """Test actual flow from research to docs team"""
    # Add teams to field
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    # Establish push flow from research to docs
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    # Research team generates information
    content = "Latest developments in AI research"
    
    # Transfer information to docs team
    await magnetic_field.transfer_information(
        source_team=source_team.name,
        target_team=target_team.name,
        content=content
    )
    
    # Verify docs team received the information
    assert "transfer" in target_team.context.shared_results
    received_result = target_team.context.shared_results["transfer"]
    assert received_result.result == content

@pytest.mark.asyncio
async def test_docs_pulling_from_research(magnetic_field, source_team, target_team):
    """Test docs team pulling information from research team"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    # Establish pull flow
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="pull"
    )
    
    # Research team has information
    content = "Python best practices guide"
    
    # Store in research team's context
    source_team.context.shared_results["research"] = ToolResult(
        tool_name="research",
        result=content,
        adhesive=AdhesiveType.GLUE,
        timestamp=datetime.now()
    )
    
    # Docs team pulls the information
    await target_team.pull_from(source_team.name)
    
    # Verify docs team has the information
    assert "research" in target_team.context.shared_results
    pulled_result = target_team.context.shared_results["research"]
    assert pulled_result.result == content

@pytest.mark.asyncio
async def test_team_repulsion(magnetic_field, source_team, target_team):
    """Test team repulsion prevents information transfer"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    # Establish repulsion
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="repel"
    )
    
    # Try to transfer information (should fail)
    with pytest.raises(ValueError, match="Cannot establish flow - teams are repelled"):
        await magnetic_field.establish_flow(
            source_team=source_team.name,
            target_team=target_team.name,
            flow_type="push"
        )
    
    # Try to transfer information between repelled teams
    content = "Test information"
    
    with pytest.raises(ValueError):
        await magnetic_field.transfer_information(
            source_team=source_team.name,
            target_team=target_team.name,
            content=content
        )

@pytest.mark.asyncio
async def test_bidirectional_collaboration(magnetic_field, source_team, target_team):
    """Test bidirectional (attract) flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    # Establish bidirectional flow (attract)
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="attract"
    )
    
    # Source team generates information
    content = "Research findings about AI collaboration patterns"
    
    # Transfer to target team
    await magnetic_field.transfer_information(
        source_team=source_team.name,
        target_team=target_team.name,
        content=content
    )
    
    # Target team generates response
    response = "Analysis of research findings"
    
    # Transfer back to source team
    await magnetic_field.transfer_information(
        source_team=target_team.name,
        target_team=source_team.name,
        content=response
    )
    
    # Verify both teams have shared information
    assert "transfer" in target_team.context.shared_results
    assert "transfer" in source_team.context.shared_results

@pytest.mark.asyncio
async def test_flow_with_prefect_config(magnetic_field, source_team, target_team):
    """Test establishing flow with Prefect configuration"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    config = PrefectTaskConfig(
        max_retries=3,
        retry_delay_seconds=10,
        timeout_seconds=300
    )
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push",
        prefect_config=config
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert magnetic_field.state.flows[flow_id].prefect_config == config
