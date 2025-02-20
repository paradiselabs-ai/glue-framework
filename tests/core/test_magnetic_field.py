"""Tests for Magnetic Field implementation"""

import pytest
from datetime import datetime
from typing import Dict, Set

from glue.magnetic.field import MagneticField
from glue.core.team import Team
from glue.core.pydantic_models import (
    TeamContext, PrefectTaskConfig, MagneticFlow
)
from glue.magnetic.models import (
    FlowEstablishedEvent,
    FlowBrokenEvent
)

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
async def test_set_push_flow(magnetic_field, source_team, target_team):
    """Test establishing a push flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id in magnetic_field.state.flows
    assert target_team.name in source_team.relationships
    assert source_team.relationships[target_team.name] == "push"

@pytest.mark.asyncio
async def test_set_pull_flow(magnetic_field, source_team, target_team):
    """Test establishing a pull flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="<-"
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id in magnetic_field.state.flows
    assert source_team.name in target_team.relationships
    assert target_team.relationships[source_team.name] == "pull"

@pytest.mark.asyncio
async def test_set_attract_flow(magnetic_field, source_team, target_team):
    """Test establishing a bidirectional flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="><"
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id in magnetic_field.state.flows
    assert target_team.name in source_team.relationships
    assert source_team.name in target_team.relationships
    assert source_team.relationships[target_team.name] == "attract"
    assert target_team.relationships[source_team.name] == "attract"

@pytest.mark.asyncio
async def test_set_repel_flow(magnetic_field, source_team, target_team):
    """Test establishing repulsion between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="<>"
    )
    
    assert target_team.name in source_team.repelled_by
    assert source_team.name in target_team.repelled_by

@pytest.mark.asyncio
async def test_break_flow(magnetic_field, source_team, target_team):
    """Test breaking a flow between teams"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    await magnetic_field.break_flow(source_team.name, target_team.name)
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id not in magnetic_field.state.flows
    assert target_team.name not in source_team.relationships
    assert source_team.name not in target_team.relationships

@pytest.mark.asyncio
async def test_break_flow_with_reason(magnetic_field, source_team, target_team):
    """Test breaking a flow with a reason"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    reason = "Test break reason"
    await magnetic_field.break_flow(source_team.name, target_team.name, reason=reason)
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id not in magnetic_field.state.flows

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
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->",
        prefect_config=config
    )
    
    flow_id = f"{source_team.name}->{target_team.name}"
    assert magnetic_field.state.flows[flow_id].prefect_config == config

@pytest.mark.asyncio
async def test_get_active_flows(magnetic_field, source_team, target_team):
    """Test getting active flows"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    flows = magnetic_field.get_active_flows()
    flow_id = f"{source_team.name}->{target_team.name}"
    assert flow_id in flows
    assert flows[flow_id].flow_type == "push"

@pytest.mark.asyncio
async def test_has_flow(magnetic_field, source_team, target_team):
    """Test checking flow existence"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    assert not magnetic_field.has_flow(source_team.name, target_team.name)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    assert magnetic_field.has_flow(source_team.name, target_team.name)

@pytest.mark.asyncio
async def test_get_flow_type(magnetic_field, source_team, target_team):
    """Test getting flow type"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    assert magnetic_field.get_flow_type(source_team.name, target_team.name) is None
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    assert magnetic_field.get_flow_type(source_team.name, target_team.name) == "push"

@pytest.mark.asyncio
async def test_event_handlers(magnetic_field, source_team, target_team):
    """Test event handling"""
    events = []
    
    def handle_flow_established(event: FlowEstablishedEvent):
        events.append(("established", event))
        
    def handle_flow_broken(event: FlowBrokenEvent):
        events.append(("broken", event))
    
    magnetic_field.register_event_handler("FlowEstablishedEvent", handle_flow_established)
    magnetic_field.register_event_handler("FlowBrokenEvent", handle_flow_broken)
    
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    # Establish flow
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    assert len(events) == 1
    assert events[0][0] == "established"
    assert events[0][1].source_team == source_team.name
    assert events[0][1].target_team == target_team.name
    assert events[0][1].flow_type == "push"
    
    # Break flow
    reason = "Test break"
    await magnetic_field.break_flow(source_team.name, target_team.name, reason=reason)
    
    assert len(events) == 2
    assert events[1][0] == "broken"
    assert events[1][1].source_team == source_team.name
    assert events[1][1].target_team == target_team.name
    assert events[1][1].reason == reason

@pytest.mark.asyncio
async def test_invalid_operator(magnetic_field, source_team, target_team):
    """Test invalid operator handling"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    with pytest.raises(ValueError):
        await magnetic_field.set_team_flow(
            source_team=source_team.name,
            target_team=target_team.name,
            operator="invalid"
        )

@pytest.mark.asyncio
async def test_break_nonexistent_flow(magnetic_field, source_team, target_team):
    """Test breaking a nonexistent flow"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    with pytest.raises(ValueError):
        await magnetic_field.break_flow(source_team.name, target_team.name)

@pytest.mark.asyncio
async def test_cleanup_flows(magnetic_field, source_team, target_team):
    """Test cleaning up all flows"""
    await magnetic_field.add_team(source_team)
    await magnetic_field.add_team(target_team)
    
    await magnetic_field.set_team_flow(
        source_team=source_team.name,
        target_team=target_team.name,
        operator="->"
    )
    
    await magnetic_field.cleanup_flows()
    
    assert len(magnetic_field.state.flows) == 0
    assert len(magnetic_field.state.repelled_teams) == 0
