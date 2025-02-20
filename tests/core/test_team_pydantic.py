"""Tests for Pydantic Team implementation"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Set

from glue.core.team import Team, TeamRole, TeamMember, TeamState
from glue.core.pydantic_models import (
    ModelConfig, ModelState, ToolResult, SmolAgentsTool,
    TeamContext
)
from glue.core.types import AdhesiveType

@pytest.fixture
def model_config():
    return ModelConfig(
        temperature=0.7,
        max_tokens=1000
    )

@pytest.fixture
def model_state(model_config):
    return ModelState(
        name="test_model",
        provider="test_provider",
        team="test_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        config=model_config
    )

@pytest.fixture
def test_tool():
    return SmolAgentsTool(
        name="test_tool",
        description="Test tool",
        inputs={"input": {"type": "string"}},
        output_type="string",
        forward_func=lambda x: x
    )

@pytest.fixture
def team_context():
    return TeamContext()

@pytest.fixture
def team(model_state, test_tool, team_context):
    return Team(
        name="test_team",
        models={"test_model": model_state},
        tools={"test_tool": test_tool},
        context=team_context
    )

@pytest.mark.asyncio
async def test_add_member(team, model_state):
    """Test adding a member to the team"""
    await team.add_member("test_model", TeamRole.LEAD)
    
    assert "test_model" in team.members
    assert team.members["test_model"].role == TeamRole.LEAD
    assert "test_tool" in team.members["test_model"].tools

@pytest.mark.asyncio
async def test_add_tool(team, test_tool):
    """Test adding a tool to the team"""
    await team.add_member("test_model", TeamRole.MEMBER)
    await team.add_tool(test_tool)
    
    assert "test_tool" in team.tools
    assert "test_tool" in team.members["test_model"].tools

@pytest.mark.asyncio
async def test_share_result(team):
    """Test sharing a result with the team"""
    result = ToolResult(
        tool_name="test_tool",
        result="test_result",
        adhesive=AdhesiveType.GLUE,
        timestamp=datetime.now()
    )
    
    await team.share_result("test_tool", result)
    assert "test_tool" in team.context.shared_results

@pytest.mark.asyncio
async def test_push_to(team):
    """Test pushing results to another team"""
    target_team = Team(name="target_team")
    team.relationships["target_team"] = AdhesiveType.GLUE
    
    result = ToolResult(
        tool_name="test_tool",
        result="test_result",
        adhesive=AdhesiveType.GLUE,
        timestamp=datetime.now()
    )
    team.context.shared_results["test_tool"] = result
    
    await team.push_to(target_team)
    assert "test_tool" in target_team.context.shared_results

@pytest.mark.asyncio
async def test_pull_from(team):
    """Test pulling results from another team"""
    source_team = Team(name="source_team")
    team.relationships["source_team"] = AdhesiveType.GLUE
    
    result = ToolResult(
        tool_name="test_tool",
        result="test_result",
        adhesive=AdhesiveType.GLUE,
        timestamp=datetime.now()
    )
    source_team.context.shared_results["test_tool"] = result
    
    await team.pull_from(source_team)
    assert "test_tool" in team.context.shared_results

def test_get_member_tools(team):
    """Test getting tools available to a member"""
    member = TeamMember(
        name="test_model",
        role=TeamRole.MEMBER,
        tools={"test_tool"}
    )
    team.members["test_model"] = member
    
    tools = team.get_member_tools("test_model")
    assert "test_tool" in tools

def test_get_active_members(team):
    """Test getting active members"""
    now = datetime.now()
    old = now - timedelta(hours=2)
    
    active_member = TeamMember(
        name="active",
        role=TeamRole.MEMBER,
        last_active=now
    )
    inactive_member = TeamMember(
        name="inactive",
        role=TeamRole.MEMBER,
        last_active=old
    )
    
    team.members["active"] = active_member
    team.members["inactive"] = inactive_member
    
    active = team.get_active_members(since=now - timedelta(hours=1))
    assert len(active) == 1
    assert active[0].name == "active"

def test_save_and_load_state(team):
    """Test saving and loading team state"""
    state = team.save_state()
    loaded_team = Team.load_state(state)
    
    assert loaded_team.name == team.name
    assert loaded_team.members == team.members
    assert loaded_team.relationships == team.relationships
    assert loaded_team.repelled_by == team.repelled_by

def test_get_team_flows(team):
    """Test getting magnetic flows"""
    team.relationships["team1"] = AdhesiveType.GLUE
    team.relationships["team2"] = AdhesiveType.VELCRO
    team.repelled_by.add("team3")
    
    flows = team.get_team_flows()
    assert flows["team1"] == "->"  # Push flow
    assert flows["team2"] == "->"  # Push flow
    assert "team3" not in flows  # Repelled team not included

def test_update_member_role(team):
    """Test updating member role"""
    lead = TeamMember(
        name="lead",
        role=TeamRole.LEAD
    )
    member = TeamMember(
        name="member",
        role=TeamRole.MEMBER
    )
    
    team.members["lead"] = lead
    team.members["member"] = member
    
    team.update_member_role("member", TeamRole.LEAD, by_member="lead")
    assert team.members["member"].role == TeamRole.LEAD
    
    with pytest.raises(ValueError):
        team.update_member_role("lead", TeamRole.MEMBER, by_member="member")
