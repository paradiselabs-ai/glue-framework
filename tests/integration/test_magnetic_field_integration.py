"""Integration tests for Magnetic Field with actual components"""

import pytest
from datetime import datetime

from glue.magnetic.field import MagneticField
from glue.core.team_pydantic import Team, TeamRole
from glue.core.model_pydantic import Model
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
    
    # Have research team search and share results
    search_result = await source_team.models["researcher"].use_tool(
        "web_search",
        AdhesiveType.GLUE,
        "Latest developments in AI"
    )
    
    # Transfer information to docs team
    await magnetic_field.transfer_information(
        source_team=source_team.name,
        target_team=target_team.name,
        content=search_result.result
    )
    
    # Verify docs team received and can use the information
    assert "transfer" in target_team.context.shared_results
    received_result = target_team.context.shared_results["transfer"]
    
    # Have docs team write file with received info
    file_result = await target_team.models["writer"].use_tool(
        "file_handler",
        AdhesiveType.TAPE,
        {
            "action": "write",
            "path": "test_output.md",
            "content": received_result.result
        }
    )
    
    assert file_result.tool_name == "file_handler"
    assert file_result.adhesive == AdhesiveType.TAPE

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
    
    # Research team generates some results
    search_result = await source_team.models["researcher"].use_tool(
        "web_search",
        AdhesiveType.GLUE,
        "Python best practices"
    )
    
    # Docs team pulls the information
    await target_team.pull_from(source_team.name)
    
    # Verify docs team has the information
    assert search_result.tool_name in target_team.context.shared_results
    pulled_result = target_team.context.shared_results[search_result.tool_name]
    assert pulled_result.result == search_result.result

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
    
    # Verify no information transfer possible
    search_result = await source_team.models["researcher"].use_tool(
        "web_search",
        AdhesiveType.GLUE,
        "Test query"
    )
    
    with pytest.raises(ValueError):
        await magnetic_field.transfer_information(
            source_team=source_team.name,
            target_team=target_team.name,
            content=search_result.result
        )

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
