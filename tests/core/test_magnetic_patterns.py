"""Test suite for advanced GLUE magnetic flow patterns"""

import pytest
from datetime import datetime
from typing import Dict, Set, Any, Optional, List
from pydantic import BaseModel, Field

from glue.core.team import Team
from glue.core.model import Model
from glue.core.types import AdhesiveType
from glue.magnetic.field import MagneticField
from glue.magnetic.rules import MagneticRules
from glue.core.team_communication import TeamCommunication
from glue.core.group_chat import GroupChat

# ==================== Advanced Pattern Models ====================
class FlowPattern(BaseModel):
    """Model for magnetic flow patterns"""
    name: str = Field(..., description="Pattern name")
    teams: List[str] = Field(..., description="Teams involved in pattern")
    flows: List[Dict[str, Any]] = Field(..., description="Flow configurations")
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PatternState(BaseModel):
    """Model for pattern execution state"""
    pattern: FlowPattern
    active_flows: Set[str] = Field(default_factory=set)
    message_counts: Dict[str, int] = Field(default_factory=dict)
    current_phase: Optional[str] = Field(default=None)

class FlowMetrics(BaseModel):
    """Model for flow performance metrics"""
    flow_id: str = Field(..., description="Flow identifier")
    message_count: int = Field(default=0)
    average_latency: float = Field(default=0.0)
    success_rate: float = Field(default=1.0)
    last_active: Optional[datetime] = Field(default=None)

# ==================== Test Fixtures ====================
@pytest.fixture
def test_models():
    """Create a set of test models with different capabilities"""
    return {
        "researcher": Model(
            name="researcher",
            provider="test",
            team="research",
            available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
            config={"temperature": 0.7}
        ),
        "analyst": Model(
            name="analyst",
            provider="test",
            team="analysis",
            available_adhesives={AdhesiveType.VELCRO},
            config={"temperature": 0.5}
        ),
        "writer": Model(
            name="writer",
            provider="test",
            team="docs",
            available_adhesives={AdhesiveType.TAPE},
            config={"temperature": 0.3}
        )
    }

@pytest.fixture
async def test_teams(test_models):
    """Create test teams with different roles"""
    teams = {
        "research": Team(
            name="research",
            models={"researcher": test_models["researcher"]}
        ),
        "analysis": Team(
            name="analysis",
            models={"analyst": test_models["analyst"]}
        ),
        "docs": Team(
            name="docs",
            models={"writer": test_models["writer"]}
        )
    }
    return teams

@pytest.fixture
def test_pattern():
    """Create a test flow pattern"""
    return FlowPattern(
        name="research_cycle",
        teams=["research", "analysis", "docs"],
        flows=[
            {
                "source": "research",
                "target": "analysis",
                "type": "push",
                "strength": 0.8
            },
            {
                "source": "analysis",
                "target": "docs",
                "type": "push",
                "strength": 0.6
            },
            {
                "source": "docs",
                "target": "research",
                "type": "pull",
                "strength": 0.4
            }
        ],
        rules=[
            {
                "type": "sequence",
                "order": ["research", "analysis", "docs"]
            },
            {
                "type": "threshold",
                "min_strength": 0.5
            }
        ]
    )

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_circular_flow_pattern(test_teams, test_pattern):
    """Test circular flow pattern between teams"""
    # Create magnetic field
    field = MagneticField()
    
    # Set up flows from pattern
    for flow in test_pattern.flows:
        field.add_flow({
            "source": flow["source"],
            "target": flow["target"],
            "type": flow["type"],
            "strength": flow["strength"]
        })
    
    # Verify flow connections
    assert field.has_flow("research", "analysis")
    assert field.has_flow("analysis", "docs")
    assert field.has_flow("docs", "research")
    
    # Verify flow strengths
    assert field.get_flow_strength("research", "analysis") == 0.8
    assert field.get_flow_strength("analysis", "docs") == 0.6
    assert field.get_flow_strength("docs", "research") == 0.4

@pytest.mark.asyncio
async def test_pattern_state_tracking(test_pattern):
    """Test pattern state tracking"""
    state = PatternState(
        pattern=test_pattern,
        active_flows={"research_to_analysis", "analysis_to_docs"},
        message_counts={
            "research_to_analysis": 5,
            "analysis_to_docs": 3,
            "docs_to_research": 0
        },
        current_phase="analysis"
    )
    
    assert len(state.active_flows) == 2
    assert state.message_counts["research_to_analysis"] == 5
    assert state.current_phase == "analysis"

@pytest.mark.asyncio
async def test_flow_metrics_tracking():
    """Test flow performance metrics tracking"""
    metrics = FlowMetrics(
        flow_id="research_to_analysis",
        message_count=10,
        average_latency=0.5,
        success_rate=0.95,
        last_active=datetime.now()
    )
    
    assert metrics.message_count == 10
    assert metrics.average_latency == 0.5
    assert metrics.success_rate == 0.95
    assert isinstance(metrics.last_active, datetime)

@pytest.mark.asyncio
async def test_pattern_rule_evaluation(test_pattern):
    """Test pattern rule evaluation"""
    def evaluate_sequence_rule(teams: List[str], current: str, next: str) -> bool:
        rule = next(r for r in test_pattern.rules if r["type"] == "sequence")
        order = rule["order"]
        current_idx = order.index(current)
        next_idx = order.index(next)
        return next_idx == (current_idx + 1) % len(order)
    
    # Test sequence rule
    assert evaluate_sequence_rule(
        test_pattern.teams,
        "research",
        "analysis"
    )
    assert evaluate_sequence_rule(
        test_pattern.teams,
        "analysis",
        "docs"
    )
    assert not evaluate_sequence_rule(
        test_pattern.teams,
        "research",
        "docs"
    )

@pytest.mark.asyncio
async def test_multi_team_collaboration(test_teams, test_pattern):
    """Test collaboration between multiple teams"""
    # Set up team communications
    comms = {
        team_name: TeamCommunication(team=team)
        for team_name, team in test_teams.items()
    }
    
    # Create pattern state
    state = PatternState(pattern=test_pattern)
    
    # Simulate research phase
    research_message = {
        "sender": "researcher",
        "content": "Initial research findings",
        "source_team": "research",
        "target_team": "analysis",
        "flow_type": "push"
    }
    
    await comms["research"].send_message(research_message)
    state.message_counts["research_to_analysis"] = 1
    state.current_phase = "analysis"
    
    assert state.message_counts["research_to_analysis"] == 1
    assert state.current_phase == "analysis"

@pytest.mark.asyncio
async def test_adhesive_flow_compatibility(test_teams):
    """Test adhesive compatibility in flow patterns"""
    research_team = test_teams["research"]
    analysis_team = test_teams["analysis"]
    
    # Check adhesive compatibility
    research_adhesives = set().union(*(
        model.available_adhesives
        for model in research_team.models.values()
    ))
    
    analysis_adhesives = set().union(*(
        model.available_adhesives
        for model in analysis_team.models.values()
    ))
    
    # Verify teams can communicate using VELCRO
    common_adhesives = research_adhesives & analysis_adhesives
    assert AdhesiveType.VELCRO in common_adhesives

@pytest.mark.asyncio
async def test_flow_strength_dynamics(test_pattern):
    """Test dynamic flow strength adjustments"""
    # Create metrics tracker
    metrics = {
        flow["source"] + "_to_" + flow["target"]: FlowMetrics(
            flow_id=flow["source"] + "_to_" + flow["target"],
            message_count=0,
            average_latency=0.0,
            success_rate=1.0
        )
        for flow in test_pattern.flows
    }
    
    # Simulate message flow and update metrics
    def update_metrics(flow_id: str, latency: float, success: bool):
        metric = metrics[flow_id]
        metric.message_count += 1
        metric.average_latency = (
            (metric.average_latency * (metric.message_count - 1) + latency)
            / metric.message_count
        )
        metric.success_rate = (
            (metric.success_rate * (metric.message_count - 1) + (1.0 if success else 0.0))
            / metric.message_count
        )
        metric.last_active = datetime.now()
        
        # Calculate new flow strength based on metrics
        return min(1.0, (1.0 - metric.average_latency) * metric.success_rate)
    
    # Test metric updates
    flow_id = "research_to_analysis"
    new_strength = update_metrics(flow_id, 0.3, True)
    assert metrics[flow_id].message_count == 1
    assert metrics[flow_id].average_latency == 0.3
    assert metrics[flow_id].success_rate == 1.0
    assert new_strength > 0.5  # Good performance should maintain high strength

@pytest.mark.asyncio
async def test_pattern_phase_transitions(test_teams, test_pattern):
    """Test phase transitions in flow patterns"""
    state = PatternState(pattern=test_pattern)
    
    # Define phase transition rules
    def can_transition(current: str, next: str, message_counts: Dict[str, int]) -> bool:
        if current == "research" and next == "analysis":
            return message_counts.get("research_to_analysis", 0) > 0
        elif current == "analysis" and next == "docs":
            return message_counts.get("analysis_to_docs", 0) > 0
        return False
    
    # Test transitions
    state.current_phase = "research"
    state.message_counts["research_to_analysis"] = 1
    
    assert can_transition(
        state.current_phase,
        "analysis",
        state.message_counts
    )
    assert not can_transition(
        state.current_phase,
        "docs",
        state.message_counts
    )
