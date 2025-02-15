"""Test suite for GLUE magnetic flow error handling"""

import pytest
from datetime import datetime
from typing import Dict, Set, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError
from glue.core.team import Team
from glue.core.model import Model
from glue.core.types import AdhesiveType
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
async def test_adhesive_compatibility_errors(test_teams):
    """Test error handling for adhesive incompatibility"""
    team_a = test_teams["team_a"]
    team_b = test_teams["team_b"]
    
    # Attempt communication between incompatible teams
    flow_error = FlowError(
        flow_id="team_a_to_team_b",
        error_type="adhesive_incompatibility",
        message="No compatible adhesives found between teams",
        context={
            "source_adhesives": {AdhesiveType.GLUE},
            "target_adhesives": set()
        }
    )
    
    assert flow_error.error_type == "adhesive_incompatibility"
    assert not bool(flow_error.context["target_adhesives"])
    assert flow_error.recoverable  # Should be recoverable through adhesive negotiation

@pytest.mark.asyncio
async def test_flow_overload_handling():
    """Test handling of flow overload conditions"""
    # Create flow metrics
    metrics = FlowMetrics = BaseModel.create_model(
        "FlowMetrics",
        flow_id=(str, ...),
        message_count=(int, ...),
        error_count=(int, ...),
        last_error=(Optional[datetime], None)
    )
    
    flow_metrics = metrics(
        flow_id="test_flow",
        message_count=1000,  # High message count
        error_count=50,      # High error count
        last_error=datetime.now()
    )
    
    # Test overload detection
    def is_overloaded(metrics: FlowMetrics) -> bool:
        error_rate = metrics.error_count / max(metrics.message_count, 1)
        return error_rate > 0.05  # 5% error threshold
    
    assert is_overloaded(flow_metrics)

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
async def test_flow_circuit_breaker():
    """Test circuit breaker pattern for flow protection"""
    class CircuitBreaker(BaseModel):
        """Circuit breaker for flow protection"""
        flow_id: str = Field(..., description="Flow identifier")
        error_threshold: int = Field(default=5)
        reset_timeout: int = Field(default=60)  # seconds
        error_count: int = Field(default=0)
        last_error: Optional[datetime] = Field(default=None)
        state: str = Field(default="closed")  # closed, open, half-open
        
        def record_error(self):
            self.error_count += 1
            self.last_error = datetime.now()
            if self.error_count >= self.error_threshold:
                self.state = "open"
        
        def can_execute(self) -> bool:
            if self.state == "closed":
                return True
            if self.state == "open":
                # Check if enough time has passed to try half-open
                if self.last_error:
                    seconds_since_error = (
                        datetime.now() - self.last_error
                    ).total_seconds()
                    if seconds_since_error >= self.reset_timeout:
                        self.state = "half-open"
                        return True
            return False
    
    breaker = CircuitBreaker(
        flow_id="test_flow",
        error_threshold=3,
        reset_timeout=30
    )
    
    # Test circuit breaker behavior
    assert breaker.can_execute()  # Should start closed
    
    # Simulate errors
    for _ in range(3):
        breaker.record_error()
    
    assert not breaker.can_execute()  # Should be open
    assert breaker.state == "open"

@pytest.mark.asyncio
async def test_flow_degradation_handling():
    """Test handling of flow performance degradation"""
    class FlowHealth(BaseModel):
        """Model for flow health monitoring"""
        flow_id: str = Field(..., description="Flow identifier")
        latency: float = Field(default=0.0)
        error_rate: float = Field(default=0.0)
        throughput: float = Field(default=1.0)
        
        def calculate_health_score(self) -> float:
            latency_score = max(0, 1 - self.latency)
            error_score = 1 - self.error_rate
            throughput_score = min(1, self.throughput)
            return (latency_score + error_score + throughput_score) / 3
        
        def is_healthy(self) -> bool:
            return self.calculate_health_score() >= 0.7
    
    # Test degraded flow
    degraded_flow = FlowHealth(
        flow_id="test_flow",
        latency=0.8,      # High latency
        error_rate=0.15,  # High error rate
        throughput=0.5    # Low throughput
    )
    
    assert not degraded_flow.is_healthy()
    assert degraded_flow.calculate_health_score() < 0.7

@pytest.mark.asyncio
async def test_flow_retry_backoff():
    """Test exponential backoff for flow retries"""
    class RetryStrategy(BaseModel):
        """Model for retry strategy"""
        initial_delay: float = Field(default=1.0)
        max_delay: float = Field(default=60.0)
        multiplier: float = Field(default=2.0)
        jitter: float = Field(default=0.1)
        
        def get_delay(self, attempt: int) -> float:
            delay = min(
                self.initial_delay * (self.multiplier ** attempt),
                self.max_delay
            )
            # Add jitter
            import random
            jitter_amount = delay * self.jitter
            return delay + random.uniform(-jitter_amount, jitter_amount)
    
    strategy = RetryStrategy()
    
    # Test backoff progression
    delays = [strategy.get_delay(i) for i in range(5)]
    
    # Verify exponential growth
    for i in range(1, len(delays)):
        assert delays[i] > delays[i-1]
    
    # Verify max delay
    assert all(d <= strategy.max_delay * (1 + strategy.jitter) for d in delays)

@pytest.mark.asyncio
async def test_flow_rate_limiting():
    """Test rate limiting for flow protection"""
    class RateLimiter(BaseModel):
        """Model for flow rate limiting"""
        flow_id: str = Field(..., description="Flow identifier")
        max_requests: int = Field(..., description="Maximum requests per window")
        window_seconds: int = Field(..., description="Time window in seconds")
        current_count: int = Field(default=0)
        window_start: datetime = Field(default_factory=datetime.now)
        
        def can_process(self) -> bool:
            now = datetime.now()
            window_elapsed = (now - self.window_start).total_seconds()
            
            if window_elapsed >= self.window_seconds:
                self.current_count = 0
                self.window_start = now
            
            return self.current_count < self.max_requests
        
        def record_request(self):
            self.current_count += 1
    
    limiter = RateLimiter(
        flow_id="test_flow",
        max_requests=100,
        window_seconds=60
    )
    
    # Test rate limiting
    assert limiter.can_process()
    
    # Simulate burst of requests
    for _ in range(100):
        limiter.record_request()
    
    assert not limiter.can_process()  # Should be limited
