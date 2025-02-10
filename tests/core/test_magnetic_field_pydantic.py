"""Tests for Pydantic Magnetic Field implementation"""

import pytest
from datetime import datetime
from typing import Dict, Set

from glue.magnetic.field_pydantic import MagneticField, FieldState
from glue.core.team_pydantic import Team, TeamRole
from glue.core.pydantic_models import (
    ModelConfig, ModelState, ToolResult, SmolAgentsTool,
    TeamContext, PrefectTaskConfig, MagneticFlow
)
from glue.core.types import AdhesiveType

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
async def test_field_initialization(magnetic_field):
    """Test magnetic field initialization"""
    assert magnetic_field.state.name == "test_field"
    assert magnetic_field.state.active == True
    assert len(magnetic_field.state.teams) == 0
    assert len(magnetic_field.state.flows) == 0

@pytest.mark.asyncio
async def test_add_team(magnetic_field, source_team):
    """Test adding a team to the field"""
    await magnetic_field.add_team(source_team)
    
    assert source_team.name in magnetic_field.state.teams
    assert magnetic_field.state.teams[source_team.name] == source_team

@pytest.mark.asyncio
async def test_remove_team(magnetic_field, source_team):
    """Test removing a team from the field"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.remove_team(source_team.name)
    
    assert source_team.name not in magnetic_field.state.teams

@pytest.mark.asyncio
async def test_establish_push_flow(magnetic_field, source_team, target_team):
    """Test establishing a push flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id in magnetic_field.state.flows
    assert target_team.name in source_team.relationships
    assert source_team.relationships[target_team.name] == AdhesiveType.GLUE

@pytest.mark.asyncio
async def test_establish_pull_flow(magnetic_field, source_team, target_team):
    """Test establishing a pull flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="pull"
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id in magnetic_field.state.flows
    assert source_team.name in target_team.relationships
    assert target_team.relationships[source_team.name] == AdhesiveType.GLUE

@pytest.mark.asyncio
async def test_establish_repel_flow(magnetic_field, source_team, target_team):
    """Test establishing repulsion between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="repel"
    )
    
    assert target_team.name in source_team.repelled_by
    assert source_team.name in target_team.repelled_by

@pytest.mark.asyncio
async def test_break_flow(magnetic_field, source_team, target_team):
    """Test breaking a flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    await magnetic_field.break_flow(source_team.name, target_team.name)
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id not in magnetic_field.state.flows
    assert target_team.name not in source_team.relationships
    assert source_team.name not in target_team.relationships

@pytest.mark.asyncio
async def test_transfer_information(magnetic_field, source_team, target_team):
    """Test transferring information between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    content = {"data": "test_data"}
    await magnetic_field.transfer_information(
        source_team=source_team.name,
        target_team=target_team.name,
        content=content
    )
    
    assert "transfer" in target_team.context.shared_results
    assert target_team.context.shared_results["transfer"].result == content

@pytest.mark.asyncio
async def test_transfer_with_custom_adhesive(magnetic_field, source_team, target_team):
    """Test transferring information with custom adhesive type"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    content = {"data": "test_data"}
    await magnetic_field.transfer_information(
        source_team=source_team.name,
        target_team=target_team.name,
        content=content,
        adhesive_type=AdhesiveType.VELCRO
    )
    
    assert "transfer" in target_team.context.shared_results
    assert target_team.context.shared_results["transfer"].adhesive == AdhesiveType.VELCRO

@pytest.mark.asyncio
async def test_get_team_flows(magnetic_field, source_team, target_team):
    """Test getting all flows for a team"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    flows = magnetic_field.get_team_flows(source_team.name)
    assert target_team.name in flows
    assert flows[target_team.name] == "->"

@pytest.mark.asyncio
async def test_get_repelled_teams(magnetic_field, source_team, target_team):
    """Test getting repelled teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="repel"
    )
    
    repelled = magnetic_field.get_repelled_teams(source_team.name)
    assert target_team.name in repelled

@pytest.mark.asyncio
async def test_is_flow_active(magnetic_field, source_team, target_team):
    """Test checking if a flow is active"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    assert not magnetic_field.is_flow_active(source_team.name, target_team.name)
    
    await magnetic_field.establish_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        flow_type="push"
    )
    
    assert magnetic_field.is_flow_active(source_team.name, target_team.name)

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
