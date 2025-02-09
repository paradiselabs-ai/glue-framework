"""Test suite for GLUE orchestrator Pydantic models"""

import pytest
from datetime import datetime
from typing import Dict, Set, Any

from glue.core.orchestrator import (
    GlueOrchestrator,
    ToolCapabilities,
    TeamCapabilities,
    MemoryRequirements,
    RoutingStrategy,
    FallbackStrategy,
    ExecutionStrategy,
    AnalysisResult,
    WorkflowContext,
    ExecutionStep,
    ExecutionPlan
)
from glue.core.team import Team
from glue.core.model import Model
from glue.core.types import AdhesiveType
from glue.tools.base import BaseTool

# Test tool class
class TestTool(BaseTool):
    def __init__(self, memory_shared: bool = False, parallel_safe: bool = True):
        super().__init__(
            name="test_tool",
            config={}
        )
        self.memory_type = "test"
        self.shared_memory = memory_shared
        self.parallel_safe = parallel_safe
        self.supported_adhesives = {"GLUE", "TAPE"}

    async def forward(self, input_data: str, **params) -> str:
        return f"Test output: {input_data}"

@pytest.fixture
def test_model():
    return Model(
        name="test_model",
        provider="test",
        team="test_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.TAPE},
        config={"temperature": 0.7}
    )

@pytest.fixture
async def test_team(test_model):
    team = Team(
        name="test_team",
        models={"test_model": test_model}
    )
    tool = TestTool()
    await team.add_tool(tool)
    return team

@pytest.mark.asyncio
async def test_tool_capabilities_model():
    """Test ToolCapabilities Pydantic model"""
    tool = TestTool(memory_shared=True, parallel_safe=False)
    
    capabilities = ToolCapabilities(
        async_support=True,
        stateful=False,
        memory=True,
        adhesives=tool.supported_adhesives,
        parallel_safe=tool.parallel_safe,
        dependencies=set(),
        dynamic=False
    )
    
    assert not capabilities.parallel_safe
    assert "GLUE" in capabilities.adhesives
    assert "TAPE" in capabilities.adhesives
    assert capabilities.memory

@pytest.mark.asyncio
async def test_team_capabilities_model():
    """Test TeamCapabilities Pydantic model"""
    tool = TestTool(memory_shared=True)
    
    tool_caps = ToolCapabilities(
        memory=True,
        adhesives=tool.supported_adhesives,
        parallel_safe=tool.parallel_safe
    )
    
    team_caps = TeamCapabilities(
        tools={"test_tool": tool_caps},
        adhesives={"GLUE", "TAPE"},
        memory={"test_tool": {"type": "test", "shared": True}},
        dynamic=False,
        parallel_safe=True
    )
    
    assert team_caps.tools["test_tool"].memory
    assert "GLUE" in team_caps.adhesives
    assert team_caps.memory["test_tool"]["shared"]

@pytest.mark.asyncio
async def test_memory_requirements_model():
    """Test MemoryRequirements Pydantic model"""
    requirements = MemoryRequirements(
        shared={"vector"},
        private={"workspace"},
        persistent={"test_tool"},
        temporary=set()
    )
    
    assert "vector" in requirements.shared
    assert "workspace" in requirements.private
    assert "test_tool" in requirements.persistent
    assert len(requirements.temporary) == 0

@pytest.mark.asyncio
async def test_routing_strategy_model():
    """Test RoutingStrategy Pydantic model"""
    strategy = RoutingStrategy(
        push={"team1"},
        pull={"team2"},
        broadcast={"team3"},
        direct={"test_tool"}
    )
    
    assert "team1" in strategy.push
    assert "team2" in strategy.pull
    assert "team3" in strategy.broadcast
    assert "test_tool" in strategy.direct

@pytest.mark.asyncio
async def test_fallback_strategy_model():
    """Test FallbackStrategy Pydantic model"""
    fallback = FallbackStrategy(
        type="dynamic_creation",
        priority=1,
        config={"max_retries": 3}
    )
    
    assert fallback.type == "dynamic_creation"
    assert fallback.priority == 1
    assert fallback.config["max_retries"] == 3

@pytest.mark.asyncio
async def test_execution_strategy_model():
    """Test ExecutionStrategy Pydantic model"""
    strategy = ExecutionStrategy(
        parallel=True,
        memory=MemoryRequirements(),
        routing=RoutingStrategy(),
        fallbacks=[
            FallbackStrategy(type="dynamic_creation", priority=1)
        ],
        adhesives={"required": {"GLUE"}},
        dynamic=True
    )
    
    assert strategy.parallel
    assert strategy.dynamic
    assert "GLUE" in strategy.adhesives["required"]
    assert len(strategy.fallbacks) == 1

@pytest.mark.asyncio
async def test_analysis_result_model():
    """Test AnalysisResult Pydantic model"""
    result = AnalysisResult(
        tools={"test_tool"},
        dependencies={"test_tool": {"file_handler"}},
        relationships={"team1": {"bidirectional": True}},
        strategy={"team1": ExecutionStrategy()}
    )
    
    assert "test_tool" in result.tools
    assert "file_handler" in result.dependencies["test_tool"]
    assert result.relationships["team1"]["bidirectional"]

@pytest.mark.asyncio
async def test_workflow_context_model(test_team):
    """Test WorkflowContext Pydantic model"""
    context = WorkflowContext(
        prompt="Test prompt",
        teams={"test_team": test_team},
        tools={"test_team": {"test_tool"}},
        models={"test_model": test_team.models["test_model"]},
        adhesives={"test_model": {AdhesiveType.GLUE}},
    )
    
    assert context.prompt == "Test prompt"
    assert "test_team" in context.teams
    assert "test_tool" in context.tools["test_team"]
    assert AdhesiveType.GLUE in context.adhesives["test_model"]

@pytest.mark.asyncio
async def test_execution_step_model():
    """Test ExecutionStep Pydantic model"""
    step = ExecutionStep(
        team="test_team",
        tools={"test_tool"},
        parallel=True,
        memory={"persistent": {"test_tool"}},
        routing={"broadcast": {"team1"}},
        fallbacks=[{"type": "retry", "priority": 1}],
        requires={"team2"}
    )
    
    assert step.team == "test_team"
    assert "test_tool" in step.tools
    assert step.parallel
    assert "test_tool" in step.memory["persistent"]
    assert "team1" in step.routing["broadcast"]
    assert "team2" in step.requires

@pytest.mark.asyncio
async def test_execution_plan_model():
    """Test ExecutionPlan Pydantic model"""
    step = ExecutionStep(
        team="test_team",
        tools={"test_tool"}
    )
    
    plan = ExecutionPlan(
        steps=[step],
        dependencies={"test_team": {"team2"}},
        strategy={"parallel": True}
    )
    
    assert len(plan.steps) == 1
    assert plan.steps[0].team == "test_team"
    assert "team2" in plan.dependencies["test_team"]
    assert plan.strategy["parallel"]

@pytest.mark.asyncio
async def test_orchestrator_model_integration(test_team):
    """Test orchestrator's use of Pydantic models"""
    orchestrator = GlueOrchestrator()
    orchestrator.register_team(test_team)
    
    # Test team capabilities analysis
    capabilities = orchestrator._analyze_team_capabilities({"test_tool"})
    assert isinstance(capabilities, TeamCapabilities)
    assert "test_tool" in capabilities.tools
    
    # Test memory requirements
    memory_reqs = orchestrator._memory_requirements(capabilities)
    assert isinstance(memory_reqs, dict)
    assert set(memory_reqs.keys()) == {"shared", "private", "persistent", "temporary"}
    
    # Test routing strategy
    routing = orchestrator._determine_routing(capabilities, {})
    assert isinstance(routing, dict)
    assert set(routing.keys()) == {"push", "pull", "broadcast", "direct"}
    
    # Test fallback strategies
    fallbacks = orchestrator._determine_fallbacks(capabilities)
    assert isinstance(fallbacks, list)
    assert all(isinstance(f, dict) for f in fallbacks)
    assert all(set(f.keys()) >= {"type", "priority"} for f in fallbacks)
