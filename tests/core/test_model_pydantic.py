"""Tests for Pydantic Model implementation"""

import pytest
from datetime import datetime
from typing import Dict, Set

from glue.core.model_pydantic import Model
from glue.core.team_pydantic import Team, TeamRole
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
def team(team_context):
    return Team(
        name="test_team",
        context=team_context
    )

@pytest.fixture
def model(model_config, team):
    model = Model(
        name="test_model",
        provider="test_provider",
        team=team.name,
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        config=model_config
    )
    model.team = team
    return model

@pytest.mark.asyncio
async def test_model_initialization(model, team):
    """Test model initialization with Pydantic state"""
    assert model.state.name == "test_model"
    assert model.state.provider == "test_provider"
    assert model.state.team == team.name
    assert AdhesiveType.GLUE in model.state.available_adhesives
    assert AdhesiveType.VELCRO in model.state.available_adhesives

@pytest.mark.asyncio
async def test_set_role(model):
    """Test setting model role"""
    role = "Research different topics and subjects online."
    model.set_role(role)
    
    assert model.state.role == role
    assert model.state.config.system_prompt == role

@pytest.mark.asyncio
async def test_use_tool(model, test_tool):
    """Test using a tool with different adhesive types"""
    # Add tool to team and model
    model.team.tools[test_tool.name] = test_tool
    model._smol_tools[test_tool.name] = test_tool
    
    # Test GLUE adhesive
    result = await model.use_tool(
        tool_name="test_tool",
        adhesive=AdhesiveType.GLUE,
        input_data="test input"
    )
    
    assert result.tool_name == "test_tool"
    assert result.result == "test input"
    assert result.adhesive == AdhesiveType.GLUE
    assert "test_tool" in model.team.context.shared_results
    
    # Test VELCRO adhesive
    result = await model.use_tool(
        tool_name="test_tool",
        adhesive=AdhesiveType.VELCRO,
        input_data="test input 2"
    )
    
    assert result.tool_name == "test_tool"
    assert result.result == "test input 2"
    assert result.adhesive == AdhesiveType.VELCRO
    assert "test_tool" in model.state.session_results

@pytest.mark.asyncio
async def test_store_interaction(model):
    """Test storing interactions in conversation history"""
    model._store_interaction("test message")
    
    assert len(model.state.conversation_history) == 1
    assert model.state.conversation_history[0].content == "test message"
    assert model.state.conversation_history[0].type == "message"

@pytest.mark.asyncio
async def test_get_relevant_context(model, test_tool):
    """Test getting relevant context"""
    # Add some history and results
    model._store_interaction("test message")
    
    result = ToolResult(
        tool_name="test_tool",
        result="test result",
        adhesive=AdhesiveType.VELCRO,
        timestamp=datetime.now()
    )
    model.state.session_results["test_tool"] = result
    
    context = model._get_relevant_context()
    
    assert len(context["recent_history"]) == 1
    assert len(context["recent_tools"]) == 1
    assert context["team"]["name"] == model.state.team

@pytest.mark.asyncio
async def test_process_message(model):
    """Test processing received messages"""
    # Test tool result message
    await model.process_message(
        sender="other_model",
        content={
            "type": "tool_result",
            "tool": "test_tool",
            "result": "test result"
        }
    )
    
    assert "test_tool" in model.team.context.shared_results
    assert model.team.context.shared_results["test_tool"].result == "test result"

@pytest.mark.asyncio
async def test_send_message(model):
    """Test sending messages between models"""
    # Add another model to team
    other_model = Model(
        name="other_model",
        provider="test_provider",
        team=model.team.name,
        available_adhesives={AdhesiveType.GLUE}
    )
    other_model.team = model.team
    model.team.models["other_model"] = other_model.state
    
    # Test sending message
    await model.send_message("other_model", "test message")
    
    # Message sending is handled by team, so just verify no errors

@pytest.mark.asyncio
async def test_message_repulsion(model):
    """Test message repulsion between models"""
    # Add repelled model
    model.state.repelled_by.add("repelled_model")
    
    with pytest.raises(ValueError):
        await model.send_message("repelled_model", "test message")
        
    with pytest.raises(ValueError):
        await model.receive_message("repelled_model", "test message")

@pytest.mark.asyncio
async def test_tool_validation(model, test_tool):
    """Test tool usage validation"""
    # Test without team
    model._team = None
    with pytest.raises(ValueError, match="not part of a team"):
        await model.use_tool("test_tool", AdhesiveType.GLUE, "test")
        
    # Test with unavailable tool
    model._team = team
    with pytest.raises(ValueError, match="not available in team"):
        await model.use_tool("missing_tool", AdhesiveType.GLUE, "test")
        
    # Test with invalid adhesive
    model.team.tools[test_tool.name] = test_tool
    model._smol_tools[test_tool.name] = test_tool
    model.state.available_adhesives = {AdhesiveType.TAPE}
    with pytest.raises(ValueError, match="cannot use GLUE adhesive"):
        await model.use_tool("test_tool", AdhesiveType.GLUE, "test")

@pytest.mark.asyncio
async def test_process_prompt_with_tool(model, test_tool):
    """Test processing prompts that use tools"""
    # Add tool that will be detected in response
    model.team.tools[test_tool.name] = test_tool
    model._smol_tools[test_tool.name] = test_tool
    
    # Override generate to return tool usage
    async def mock_generate(prompt: str) -> str:
        return f"Using test_tool with input: {prompt}"
    model.generate = mock_generate
    
    # Process prompt
    result = await model.process("test input")
    
    # Tool execution is handled by executor, so result will be the generated response
    assert "test_tool" in result.lower()
    assert len(model.state.conversation_history) == 1

@pytest.mark.asyncio
async def test_process_prompt_without_tool(model):
    """Test processing prompts without tool usage"""
    # Override generate to return simple response
    async def mock_generate(prompt: str) -> str:
        return f"Response: {prompt}"
    model.generate = mock_generate
    
    # Process prompt
    result = await model.process("test input")
    
    assert result == "Response: test input"
    assert len(model.state.conversation_history) == 1
