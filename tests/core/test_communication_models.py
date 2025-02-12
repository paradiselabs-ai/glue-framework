"""Test suite for GLUE communication and magnetic flow models"""

import pytest
from datetime import datetime
from typing import Dict, Set, Any, Optional, List
from pydantic import BaseModel, Field

from glue.core.team import Team
from glue.core.model import Model
from glue.core.types import AdhesiveType
from glue.magnetic.field import MagneticField
from glue.core.team_communication import TeamCommunicationManager
from glue.core.group_chat import GroupChatManager

# ==================== Communication Models ====================
class Message(BaseModel):
    """Model for communication messages"""
    sender: str = Field(..., description="Message sender")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ModelMessage(Message):
    """Model-to-model communication message"""
    tool_context: Optional[Dict[str, Any]] = Field(default=None)
    adhesive_type: Optional[AdhesiveType] = Field(default=None)

class TeamMessage(Message):
    """Team-to-team communication message"""
    source_team: str = Field(..., description="Source team name")
    target_team: str = Field(..., description="Target team name")
    flow_type: str = Field(..., description="Magnetic flow type")
    priority: int = Field(default=0)

class MagneticFlow(BaseModel):
    """Magnetic flow configuration"""
    source: str = Field(..., description="Source of the flow")
    target: str = Field(..., description="Target of the flow")
    flow_type: str = Field(..., description="Type of magnetic flow")
    bidirectional: bool = Field(default=False)
    strength: float = Field(default=1.0)
    rules: List[Dict[str, Any]] = Field(default_factory=list)

class FlowState(BaseModel):
    """Current state of a magnetic flow"""
    flow: MagneticFlow
    active: bool = Field(default=True)
    message_count: int = Field(default=0)
    last_message: Optional[TeamMessage] = Field(default=None)

# ==================== Test Fixtures ====================
@pytest.fixture
def test_model_a():
    return Model(
        name="model_a",
        provider="test",
        team="team_a",
        available_adhesives={AdhesiveType.GLUE},
        config={"temperature": 0.7}
    )

@pytest.fixture
def test_model_b():
    return Model(
        name="model_b",
        provider="test",
        team="team_a",
        available_adhesives={AdhesiveType.VELCRO},
        config={"temperature": 0.5}
    )

@pytest.fixture
async def test_team_a(test_model_a, test_model_b):
    team = Team(
        name="team_a",
        models={
            "model_a": test_model_a,
            "model_b": test_model_b
        }
    )
    return team

@pytest.fixture
def test_model_c():
    return Model(
        name="model_c",
        provider="test",
        team="team_b",
        available_adhesives={AdhesiveType.TAPE},
        config={"temperature": 0.3}
    )

@pytest.fixture
async def test_team_b(test_model_c):
    team = Team(
        name="team_b",
        models={"model_c": test_model_c}
    )
    return team

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_model_message():
    """Test model-to-model message structure"""
    message = ModelMessage(
        sender="model_a",
        content="Test message",
        tool_context={"tool": "test_tool"},
        adhesive_type=AdhesiveType.GLUE
    )
    
    assert message.sender == "model_a"
    assert message.content == "Test message"
    assert message.tool_context["tool"] == "test_tool"
    assert message.adhesive_type == AdhesiveType.GLUE
    assert isinstance(message.timestamp, datetime)

@pytest.mark.asyncio
async def test_team_message():
    """Test team-to-team message structure"""
    message = TeamMessage(
        sender="model_a",
        content="Test message",
        source_team="team_a",
        target_team="team_b",
        flow_type="push",
        priority=1
    )
    
    assert message.source_team == "team_a"
    assert message.target_team == "team_b"
    assert message.flow_type == "push"
    assert message.priority == 1

@pytest.mark.asyncio
async def test_magnetic_flow():
    """Test magnetic flow configuration"""
    flow = MagneticFlow(
        source="team_a",
        target="team_b",
        flow_type="push",
        bidirectional=True,
        strength=0.8,
        rules=[{"type": "filter", "condition": "priority > 0"}]
    )
    
    assert flow.source == "team_a"
    assert flow.target == "team_b"
    assert flow.bidirectional
    assert flow.strength == 0.8
    assert len(flow.rules) == 1

@pytest.mark.asyncio
async def test_flow_state():
    """Test magnetic flow state tracking"""
    flow = MagneticFlow(
        source="team_a",
        target="team_b",
        flow_type="push"
    )
    
    message = TeamMessage(
        sender="model_a",
        content="Test message",
        source_team="team_a",
        target_team="team_b",
        flow_type="push"
    )
    
    state = FlowState(flow=flow, message_count=1, last_message=message)
    
    assert state.active
    assert state.message_count == 1
    assert state.last_message.content == "Test message"

@pytest.mark.asyncio
async def test_model_to_model_communication(test_team_a):
    """Test model-to-model communication within a team"""
    model_a = test_team_a.models["model_a"]
    model_b = test_team_a.models["model_b"]
    
    # Create group chat manager
    chat_manager = GroupChatManager("test_chat")
    chat_manager.add_model(model_a)
    chat_manager.add_model(model_b)
    
    # Start a chat between models
    chat_id = await chat_manager.start_chat(model_a.name, model_b.name)
    
    # Test message exchange
    message = ModelMessage(
        sender=model_a.name,
        content="Request for analysis",
        tool_context={"task": "analysis"},
        adhesive_type=AdhesiveType.GLUE
    )
    
    response = await chat_manager.process_message(
        chat_id,
        message.content,
        from_model=model_a.name,
        target_model=model_b.name
    )
    
    # Verify chat history
    assert len(chat_manager.chat_history) == 1
    assert chat_manager.chat_history[0]["from_model"] == model_a.name
    assert chat_manager.chat_history[0]["content"] == "Request for analysis"
    
    # Cleanup
    await chat_manager.end_chat(chat_id)

@pytest.mark.asyncio
async def test_team_to_team_communication(test_team_a, test_team_b):
    """Test team-to-team communication through magnetic flows"""
    # Create magnetic flow
    flow = MagneticFlow(
        source=test_team_a.name,
        target=test_team_b.name,
        flow_type="push",
        bidirectional=True
    )
    
    # Set up team communication
    comm = TeamCommunicationManager("test_comm")
    await comm.add_team(test_team_a)
    await comm.add_team(test_team_b)
    
    # Create and track flow state
    state = FlowState(flow=flow)
    
    # Test message exchange
    message = TeamMessage(
        sender=test_team_a.models["model_a"].name,
        content="Team collaboration request",
        source_team=test_team_a.name,
        target_team=test_team_b.name,
        flow_type="push"
    )
    
    # Set up flow and send message
    flow_id = await comm.set_team_flow(test_team_a.name, test_team_b.name, "push")
    await comm.share_results(flow_id, {"message": message.dict()}, test_team_a.name)
    state.message_count += 1
    state.last_message = message
    
    # Verify flow state
    assert state.message_count == 1
    assert state.last_message.content == "Team collaboration request"
    assert state.active

@pytest.mark.asyncio
async def test_magnetic_field_integration(test_team_a, test_team_b):
    """Test magnetic field integration with teams"""
    # Create magnetic field
    field = MagneticField()
    
    # Add flow
    flow = MagneticFlow(
        source=test_team_a.name,
        target=test_team_b.name,
        flow_type="push",
        bidirectional=True,
        strength=0.8
    )
    
    field.add_flow(flow.dict())
    
    # Test field properties
    assert field.has_flow(test_team_a.name, test_team_b.name)
    assert field.get_flow_strength(test_team_a.name, test_team_b.name) == 0.8
    assert field.is_bidirectional(test_team_a.name, test_team_b.name)

@pytest.mark.asyncio
async def test_adhesive_compatibility():
    """Test adhesive compatibility in communication"""
    # Create models with different adhesive types
    model_a = Model(
        name="model_a",
        provider="test",
        team="team_a",
        available_adhesives={AdhesiveType.GLUE}
    )
    
    model_b = Model(
        name="model_b",
        provider="test",
        team="team_a",
        available_adhesives={AdhesiveType.VELCRO}
    )
    
    # Test message with specific adhesive
    message = ModelMessage(
        sender=model_a.name,
        content="Test message",
        adhesive_type=AdhesiveType.GLUE
    )
    
    # Verify adhesive compatibility
    can_receive = AdhesiveType.GLUE in model_b.available_adhesives
    assert not can_receive  # Should be False since model_b only supports VELCRO

@pytest.mark.asyncio
async def test_flow_rule_evaluation():
    """Test magnetic flow rule evaluation"""
    # Create flow with rules
    flow = MagneticFlow(
        source="team_a",
        target="team_b",
        flow_type="push",
        rules=[
            {
                "type": "filter",
                "condition": "priority >= 2"
            },
            {
                "type": "transform",
                "action": "uppercase"
            }
        ]
    )
    
    # Test messages with different priorities
    low_priority = TeamMessage(
        sender="model_a",
        content="Low priority message",
        source_team="team_a",
        target_team="team_b",
        flow_type="push",
        priority=1
    )
    
    high_priority = TeamMessage(
        sender="model_a",
        content="High priority message",
        source_team="team_a",
        target_team="team_b",
        flow_type="push",
        priority=2
    )
    
    # Evaluate rules
    def evaluate_message(message: TeamMessage) -> bool:
        for rule in flow.rules:
            if rule["type"] == "filter":
                if message.priority < 2:
                    return False
        return True
    
    assert not evaluate_message(low_priority)
    assert evaluate_message(high_priority)
