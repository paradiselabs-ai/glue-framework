"""Test suite for GLUE magnetic flow error handling"""

import pytest
from datetime import datetime
from typing import Dict, Set, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError
from glue.core.team import Team
from glue.core.model import Model
from glue.magnetic.field import MagneticField
from glue.magnetic.rules import MagneticRules

# ==================== Error Models ====================
class FlowError(BaseModel):
    """Model for flow errors"""
    flow_id: str = Field(..., description="Flow identifier")
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = Field(default=True)

class RecoveryAction(BaseModel):
    """Model for flow recovery actions"""
    error: FlowError
    action_type: str = Field(..., description="Type of recovery action")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)

# ==================== Test Fixtures ====================
@pytest.fixture
def test_models():
    """Create test models with potential error conditions"""
    return {
        "model_a": Model(
            name="model_a",
            provider="test",
            team="team_a",
            available_adhesives={AdhesiveType.GLUE},
            config={"temperature": 0.7}
        ),
        "model_b": Model(
            name="model_b",
            provider="test",
            team="team_b",
            available_adhesives=set(),  # No adhesives - should cause errors
            config={"temperature": 0.5}
        )
    }

@pytest.fixture
async def test_teams(test_models):
    """Create test teams for error scenarios"""
    teams = {
        "team_a": Team(
            name="team_a",
            models={"model_a": test_models["model_a"]}
        ),
        "team_b": Team(
            name="team_b",
            models={"model_b": test_models["model_b"]}
        )
    }
    return teams

# ==================== Tests ====================
@pytest.mark.asyncio
async def test_flow_validation_errors():
    """Test validation errors in flow configuration"""
    # Test invalid flow strength
    with pytest.raises(ValidationError):
        MagneticFlow = BaseModel.create_model(
            "MagneticFlow",
            source=(str, ...),
            target=(str, ...),
            strength=(float, ...),
        )
        
        flow = MagneticFlow(
            source="team_a",
            target="team_b",
            strength=1.5  # Invalid: should be <= 1.0
        )

@pytest.mark.asyncio
async def test_flow_overload_handling(test_teams):
    """Test handling of flow overload conditions"""
    field = MagneticField(name="test_field")
    team_a = test_teams["team_a"]
    team_b = test_teams["team_b"]
    
    # Register teams
    await field.add_team(team_a)
    await field.add_team(team_b)
    
    # Set up flow
    flow_id = f"{team_a.name}_to_{team_b.name}"
    await field.set_team_flow(team_a.name, team_b.name, "->")
    
    # Get initial health metrics
    status = field.debug.protection_status.get(flow_id, {})
    health = status.get("health", {})
    
    # Verify initial state
    assert health.get("error_rate", 0.0) == 0.0
    assert health.get("throughput", 1.0) == 1.0
    
    # Simulate overload
    if flow_id in field._health_monitors:
        monitor = field._health_monitors[flow_id]
        monitor.error_rate = 0.06  # Above 5% threshold
        monitor.throughput = 0.5   # Reduced throughput
        
    # Update debug info
    field.debug.update_protection_status(
        flow_id,
        field._circuit_breakers.get(flow_id),
        field._rate_limiters.get(flow_id),
        field._retry_strategies.get(flow_id),
        field._health_monitors.get(flow_id)
    )
    
    # Get updated health metrics
    status = field.debug.protection_status.get(flow_id, {})
    health = status.get("health", {})
    
    # Verify overload state
    assert health.get("error_rate", 0.0) > 0.05  # Above 5% threshold
    assert health.get("throughput", 1.0) < 1.0    # Reduced throughput

@pytest.mark.asyncio
async def test_recovery_action_validation():
    """Test validation of recovery actions"""
    error = FlowError(
        flow_id="test_flow",
        error_type="connection_lost",
        message="Connection to team lost",
        recoverable=True
    )
    
    # Test valid recovery action
    action = RecoveryAction(
        error=error,
        action_type="reconnect",
        parameters={"timeout": 30},
        max_retries=3
    )
    
    assert action.action_type == "reconnect"
    assert action.retry_count == 0
    assert action.max_retries == 3
    
    # Test retry increment
    def increment_retry(action: RecoveryAction) -> bool:
        if action.retry_count >= action.max_retries:
            return False
        action.retry_count += 1
        return True
    
    assert increment_retry(action)
    assert action.retry_count == 1

@pytest.mark.asyncio
async def test_flow_circuit_breaker(test_teams):
    """Test circuit breaker pattern for flow protection"""
    field = MagneticField(name="test_field")
    team_a = test_teams["team_a"]
    team_b = test_teams["team_b"]
    
    # Register teams
    await field.add_team(team_a)
    await field.add_team(team_b)
    
    # Set up flow
    flow_id = f"{team_a.name}_to_{team_b.name}"
    await field.set_team_flow(team_a.name, team_b.name, "->")
    
    # Get initial protection status
    status = field.debug.protection_status.get(flow_id, {})
    circuit_breaker = status.get("circuit_breaker", {})
    
    # Verify initial state
    assert not circuit_breaker.get("is_open", False)
    assert circuit_breaker.get("error_count", 0) == 0
    
    # Simulate errors by updating protection status
    for _ in range(3):
        field.debug.update_protection_status(
            flow_id,
            field._circuit_breakers.get(flow_id),
            field._rate_limiters.get(flow_id),
            field._retry_strategies.get(flow_id),
            field._health_monitors.get(flow_id)
        )
        if flow_id in field._circuit_breakers:
            field._circuit_breakers[flow_id].record_error()
    
    # Get updated status
    status = field.debug.protection_status.get(flow_id, {})
    circuit_breaker = status.get("circuit_breaker", {})
    
    # Verify breaker is open
    assert circuit_breaker.get("is_open", False)
    assert circuit_breaker.get("error_count", 0) >= 3

@pytest.mark.asyncio
async def test_flow_degradation_handling(test_teams):
    """Test handling of flow performance degradation"""
    field = MagneticField(name="test_field")
    team_a = test_teams["team_a"]
    team_b = test_teams["team_b"]
    
    # Register teams
    await field.add_team(team_a)
    await field.add_team(team_b)
    
    # Set up flow
    flow_id = f"{team_a.name}_to_{team_b.name}"
    await field.set_team_flow(team_a.name, team_b.name, "->")
    
    # Get initial health metrics
    status = field.debug.protection_status.get(flow_id, {})
    health = status.get("health", {})
    
    # Verify initial health
    assert health.get("latency", 0.0) == 0.0
    assert health.get("error_rate", 0.0) == 0.0
    assert health.get("throughput", 1.0) == 1.0
    
    # Simulate degradation
    if flow_id in field._health_monitors:
        monitor = field._health_monitors[flow_id]
        monitor.latency = 0.8
        monitor.error_rate = 0.15
        monitor.throughput = 0.5
        
    # Update debug info
    field.debug.update_protection_status(
        flow_id,
        field._circuit_breakers.get(flow_id),
        field._rate_limiters.get(flow_id),
        field._retry_strategies.get(flow_id),
        field._health_monitors.get(flow_id)
    )
    
    # Get updated health metrics
    status = field.debug.protection_status.get(flow_id, {})
    health = status.get("health", {})
    
    # Verify degraded state
    assert health.get("latency", 0.0) >= 0.8
    assert health.get("error_rate", 0.0) >= 0.15
    assert health.get("throughput", 1.0) <= 0.5

@pytest.mark.asyncio
async def test_flow_retry_backoff(test_teams):
    """Test exponential backoff for flow retries"""
    field = MagneticField(name="test_field")
    team_a = test_teams["team_a"]
    team_b = test_teams["team_b"]
    
    # Register teams
    await field.add_team(team_a)
    await field.add_team(team_b)
    
    # Set up flow
    flow_id = f"{team_a.name}_to_{team_b.name}"
    await field.set_team_flow(team_a.name, team_b.name, "->")
    
    # Get initial retry strategy status
    status = field.debug.protection_status.get(flow_id, {})
    retry_strategy = status.get("retry_strategy", {})
    
    # Verify initial state
    assert retry_strategy.get("current_retries", 0) == 0
    assert retry_strategy.get("max_retries", 0) > 0
    assert retry_strategy.get("backoff_factor", 0) > 0
    
    # Simulate retries
    if flow_id in field._retry_strategies:
        strategy = field._retry_strategies[flow_id]
        for _ in range(3):
            strategy.current_retries += 1
            
    # Update debug info
    field.debug.update_protection_status(
        flow_id,
        field._circuit_breakers.get(flow_id),
        field._rate_limiters.get(flow_id),
        field._retry_strategies.get(flow_id),
        field._health_monitors.get(flow_id)
    )
    
    # Get updated status
    status = field.debug.protection_status.get(flow_id, {})
    retry_strategy = status.get("retry_strategy", {})
    
    # Verify retry progression
    assert retry_strategy.get("current_retries", 0) >= 3
    assert retry_strategy.get("current_retries", 0) <= retry_strategy.get("max_retries", 0)

@pytest.mark.asyncio
async def test_flow_rate_limiting(test_teams):
    """Test rate limiting for flow protection"""
    field = MagneticField(name="test_field")
    team_a = test_teams["team_a"]
    team_b = test_teams["team_b"]
    
    # Register teams
    await field.add_team(team_a)
    await field.add_team(team_b)
    
    # Set up flow
    flow_id = f"{team_a.name}_to_{team_b.name}"
    await field.set_team_flow(team_a.name, team_b.name, "->")
    
    # Get initial rate limiter status
    status = field.debug.protection_status.get(flow_id, {})
    rate_limiter = status.get("rate_limiter", {})
    
    # Verify initial state
    assert rate_limiter.get("current_rate", 0) == 0
    assert rate_limiter.get("max_requests", 0) > 0
    
    # Simulate requests
    if flow_id in field._rate_limiters:
        limiter = field._rate_limiters[flow_id]
        for _ in range(100):
            limiter.record_request()
            
    # Update debug info
    field.debug.update_protection_status(
        flow_id,
        field._circuit_breakers.get(flow_id),
        field._rate_limiters.get(flow_id),
        field._retry_strategies.get(flow_id),
        field._health_monitors.get(flow_id)
    )
    
    # Get updated status
    status = field.debug.protection_status.get(flow_id, {})
    rate_limiter = status.get("rate_limiter", {})
    
    # Verify rate limit exceeded
    assert rate_limiter.get("current_rate", 0) >= rate_limiter.get("max_requests", 0)
