"""Team functionality tests"""

import pytest
from datetime import datetime
from typing import Set

from glue.core.team import Team, TeamMember, TeamRole
from glue.core.types import AdhesiveType, ToolResult
from glue.tools.web_search import WebSearchTool
from glue.tools.file_handler import FileHandlerTool
from glue.providers.openrouter import OpenRouterProvider

@pytest.fixture
def basic_team():
    """Create a basic team for testing"""
    return Team(name="test_team")

@pytest.fixture
def web_search_tool():
    """Create web search tool for testing"""
    return WebSearchTool()

@pytest.fixture
def file_handler_tool():
    """Create file handler tool for testing"""
    return FileHandlerTool()

@pytest.fixture
def test_model():
    """Create test model for testing"""
    return OpenRouterProvider(
        name="test_model",
        provider="openrouter",
        team="test_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        api_key="test_key"
    )

def test_team_creation(basic_team):
    """Test basic team creation"""
    assert basic_team.name == "test_team"
    assert len(basic_team.members) == 0
    assert len(basic_team.tools) == 0

def test_add_member(basic_team, test_model):
    """Test adding a member to team"""
    # Add member
    basic_team.add_member(test_model.name, role=TeamRole.MEMBER)
    
    # Verify member added
    assert test_model.name in basic_team.members
    assert basic_team.members[test_model.name].role == TeamRole.MEMBER

def test_add_tool(basic_team, web_search_tool):
    """Test adding a tool to team"""
    # Add tool
    basic_team.add_tool("web_search", web_search_tool)
    
    # Verify tool added
    assert "web_search" in basic_team.tools

def test_tool_distribution(basic_team, test_model, web_search_tool):
    """Test tool distribution to team members"""
    # Add tool and member
    basic_team.add_tool("web_search", web_search_tool)
    basic_team.add_member(test_model.name)
    
    # Verify tool available to member
    member_tools = basic_team.get_member_tools(test_model.name)
    assert "web_search" in member_tools

def test_glue_adhesive(basic_team, test_model, web_search_tool):
    """Test GLUE adhesive binding"""
    # Setup
    basic_team.add_tool("web_search", web_search_tool)
    basic_team.add_member(test_model.name)
    
    # Create test result
    result = ToolResult(
        tool_name="web_search",
        result="test result",
        adhesive=AdhesiveType.GLUE,
        timestamp=datetime.now()
    )
    
    # Share result
    basic_team.share_result("web_search", result)
    
    # Verify result shared
    assert "web_search" in basic_team.shared_results
    assert basic_team.shared_results["web_search"] == result

def test_velcro_adhesive(basic_team, test_model, web_search_tool):
    """Test VELCRO adhesive binding"""
    # Setup
    basic_team.add_tool("web_search", web_search_tool)
    basic_team.add_member(test_model.name)
    
    # Create test result
    result = ToolResult(
        tool_name="web_search",
        result="test result",
        adhesive=AdhesiveType.VELCRO,
        timestamp=datetime.now()
    )
    
    # Use tool with VELCRO
    test_model._session_results["web_search"] = result
    
    # Verify result not shared
    assert "web_search" not in basic_team.shared_results

def test_team_communication(basic_team):
    """Test team member communication"""
    # Add members
    basic_team.add_member("model1", role=TeamRole.LEAD)
    basic_team.add_member("model2", role=TeamRole.MEMBER)
    
    # Test message sending
    basic_team.send_message("model1", "model2", "test message")
    
    # Verify message delivery (would be handled by communication system)
    assert basic_team.members["model1"].last_active is not None
    assert basic_team.members["model2"].last_active is not None

def test_magnetic_attraction():
    """Test magnetic attraction between teams"""
    # Create teams
    team1 = Team(name="team1")
    team2 = Team(name="team2")
    
    # Set attraction
    team1.set_relationship("team2", None)  # None = adhesive-agnostic
    
    # Verify relationship
    assert "team2" in team1._relationships

def test_magnetic_repulsion():
    """Test magnetic repulsion between teams"""
    # Create teams
    team1 = Team(name="team1")
    team2 = Team(name="team2")
    
    # Set repulsion
    team1.repel("team2")
    
    # Verify repulsion
    assert "team2" in team1._repelled_by
    assert "team2" not in team1._relationships

def test_team_cleanup(basic_team, test_model, web_search_tool):
    """Test team cleanup"""
    # Setup
    basic_team.add_tool("web_search", web_search_tool)
    basic_team.add_member(test_model.name)
    
    # Cleanup
    basic_team.cleanup()
    
    # Verify cleanup
    assert len(basic_team.members) == 0
    assert len(basic_team.tools) == 0
    assert len(basic_team.shared_results) == 0

def test_invalid_operations(basic_team):
    """Test invalid operations"""
    # Test invalid member
    with pytest.raises(ValueError):
        basic_team.get_member_tools("nonexistent")
    
    # Test invalid tool
    with pytest.raises(ValueError):
        basic_team.add_tool("invalid", None)
    
    # Test invalid relationship
    with pytest.raises(ValueError):
        basic_team.set_relationship("nonexistent", AdhesiveType.GLUE)
