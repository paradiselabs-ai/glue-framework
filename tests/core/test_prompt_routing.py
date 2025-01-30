"""Test prompt intention detection and routing"""

import pytest
from glue.core.app import GlueApp
from glue.core.team import Team
from glue.core.types import AdhesiveType
from glue.providers.openrouter import OpenRouterProvider
from glue.tools.web_search import WebSearchTool
from glue.tools.code_interpreter import CodeInterpreterTool

@pytest.fixture
async def test_app():
    """Create test app with multiple teams"""
    app = GlueApp("test_app")
    
    # Create research team
    research_team = Team("research")
    research_team.add_tool("web_search", WebSearchTool())
    research_model = OpenRouterProvider(
        name="researcher",
        provider="openrouter",
        team="research",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test_key"
    )
    research_team.add_member(research_model.name, role="LEAD")
    
    # Create coding team
    coding_team = Team("coding")
    coding_team.add_tool("code_interpreter", CodeInterpreterTool())
    coding_model = OpenRouterProvider(
        name="coder",
        provider="openrouter",
        team="coding",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test_key"
    )
    coding_team.add_member(coding_model.name, role="LEAD")
    
    # Add teams to app
    app.add_team(research_team)
    app.add_team(coding_team)
    
    try:
        yield app
    finally:
        await app.cleanup()

@pytest.mark.asyncio
async def test_research_prompt_routing(test_app):
    """Test routing of research-related prompts"""
    # Research prompt
    result = await test_app.process_prompt(
        "Research the latest developments in quantum computing"
    )
    
    # Verify routed to research team
    assert test_app.last_active_team == "research"
    assert "researcher" in test_app.get_field_resources("research")

@pytest.mark.asyncio
async def test_coding_prompt_routing(test_app):
    """Test routing of coding-related prompts"""
    # Coding prompt
    result = await test_app.process_prompt(
        "Write a Python function to calculate Fibonacci numbers"
    )
    
    # Verify routed to coding team
    assert test_app.last_active_team == "coding"
    assert "coder" in test_app.get_field_resources("coding")

@pytest.mark.asyncio
async def test_multi_team_prompt_routing(test_app):
    """Test routing of prompts requiring multiple teams"""
    # Prompt requiring both research and coding
    result = await test_app.process_prompt(
        "Research machine learning algorithms and implement one in Python"
    )
    
    # Verify both teams activated
    resources = test_app.get_active_resources()
    assert "researcher" in [r.name for r in resources]
    assert "coder" in [r.name for r in resources]

@pytest.mark.asyncio
async def test_prompt_context_persistence(test_app):
    """Test persistence of prompt context for routing"""
    # Initial research prompt
    await test_app.process_prompt(
        "Research quantum computing basics"
    )
    
    # Follow-up prompt without explicit context
    result = await test_app.process_prompt(
        "Now explain the key concepts"
    )
    
    # Verify maintained research context
    assert test_app.last_active_team == "research"
    assert "researcher" in test_app.get_field_resources("research")

@pytest.mark.asyncio
async def test_prompt_rerouting(test_app):
    """Test rerouting prompts based on conversation flow"""
    # Start with research
    await test_app.process_prompt(
        "Research sorting algorithms"
    )
    
    # Transition to implementation
    result = await test_app.process_prompt(
        "Implement the quicksort algorithm we just researched"
    )
    
    # Verify rerouted to coding team
    assert test_app.last_active_team == "coding"
    assert "coder" in test_app.get_field_resources("coding")

@pytest.mark.asyncio
async def test_invalid_prompt_handling(test_app):
    """Test handling of invalid or ambiguous prompts"""
    # Test empty prompt
    with pytest.raises(ValueError):
        await test_app.process_prompt("")
    
    # Test ambiguous prompt
    result = await test_app.process_prompt(
        "Help me with my project"
    )
    # Should request clarification or use default routing
    assert result.needs_clarification or test_app.last_active_team is not None

@pytest.mark.asyncio
async def test_prompt_priority_routing(test_app):
    """Test routing based on prompt priority and team availability"""
    # Simulate busy research team
    research_team = test_app.teams["research"]
    research_team.busy = True
    
    # Send research prompt
    result = await test_app.process_prompt(
        "Research quantum computing, urgent!"
    )
    
    # Verify proper handling of busy team
    assert result.queued or result.rerouted
    assert hasattr(result, 'estimated_wait') or hasattr(result, 'alternate_team')
