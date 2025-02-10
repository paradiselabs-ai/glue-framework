"""GLUE Framework Debug Endpoints"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..magnetic.field import MagneticField

class FlowDebugInfo(BaseModel):
    """Debug information for a flow"""
    flow_id: str
    source_team: str
    target_team: str
    flow_type: str
    active: bool
    message_count: int
    last_active: Optional[datetime]
    error_count: int
    last_error: Optional[datetime]
    strength: float = Field(ge=0.0, le=1.0)
    protection_status: Dict[str, Any]

class PatternDebugInfo(BaseModel):
    """Debug information for a flow pattern"""
    name: str
    teams: list[str]
    current_phase: Optional[str]
    active_flows: set[str]
    message_counts: Dict[str, int]
    rules: list[Dict[str, Any]]

class FieldDebugInfo(BaseModel):
    """Debug information for a magnetic field"""
    name: str
    active_flows: Dict[str, FlowDebugInfo]
    repelled_teams: set[str]
    registered_teams: set[str]
    child_fields: list[str]
    active_patterns: Dict[str, PatternDebugInfo]
    timestamp: datetime = Field(default_factory=datetime.now)

class DebugEndpoints:
    """Debug endpoints for inspecting framework state"""
    
    @staticmethod
    def get_flow_debug_info(field: 'MagneticField', flow_id: str) -> Optional[FlowDebugInfo]:
        """Get debug information for a specific flow"""
        flow_state = field.state.active_flows.get(flow_id)
        if not flow_state:
            return None
            
        # Get protection mechanism status
        protection_status = {
            "circuit_breaker": {
                "state": field._circuit_breakers[flow_id].state if flow_id in field._circuit_breakers else None,
                "error_count": field._circuit_breakers[flow_id].error_count if flow_id in field._circuit_breakers else 0
            },
            "rate_limiter": {
                "current_count": field._rate_limiters[flow_id].current_count if flow_id in field._rate_limiters else 0,
                "window_start": field._rate_limiters[flow_id].window_start if flow_id in field._rate_limiters else None
            },
            "health": {
                "latency": field._health_monitors[flow_id].latency if flow_id in field._health_monitors else 0.0,
                "error_rate": field._health_monitors[flow_id].error_rate if flow_id in field._health_monitors else 0.0,
                "throughput": field._health_monitors[flow_id].throughput if flow_id in field._health_monitors else 0.0
            }
        }
        
        return FlowDebugInfo(
            flow_id=flow_id,
            source_team=flow_state.config.source,
            target_team=flow_state.config.target,
            flow_type=flow_state.config.flow_type,
            active=flow_state.active,
            message_count=flow_state.message_count,
            last_active=flow_state.last_active,
            error_count=flow_state.error_count,
            last_error=flow_state.last_error,
            strength=flow_state.config.strength,
            protection_status=protection_status
        )
    
    @staticmethod
    def get_pattern_debug_info(field: 'MagneticField', pattern_name: str) -> Optional[PatternDebugInfo]:
        """Get debug information for a specific pattern"""
        pattern_state = field._active_patterns.get(pattern_name)
        if not pattern_state:
            return None
            
        return PatternDebugInfo(
            name=pattern_state.pattern.name,
            teams=pattern_state.pattern.teams,
            current_phase=pattern_state.current_phase,
            active_flows=pattern_state.active_flows,
            message_counts=pattern_state.message_counts,
            rules=pattern_state.pattern.rules
        )

    @staticmethod
    def get_field_debug_info(field: 'MagneticField') -> FieldDebugInfo:
        """Get debug information for a magnetic field"""
        active_flows = {}
        for flow_id in field.state.active_flows:
            flow_info = DebugEndpoints.get_flow_debug_info(field, flow_id)
            if flow_info:
                active_flows[flow_id] = flow_info
                
        # Get active patterns
        active_patterns = {}
        for pattern_name in field._active_patterns:
            pattern_info = DebugEndpoints.get_pattern_debug_info(field, pattern_name)
            if pattern_info:
                active_patterns[pattern_name] = pattern_info
        
        return FieldDebugInfo(
            name=field.config.name,
            active_flows=active_flows,
            repelled_teams=field.state.repelled_teams,
            registered_teams=field.state.registered_teams,
            child_fields=list(field.state.child_fields),
            active_patterns=active_patterns
        )
    
    @staticmethod
    def get_flow_metrics(field: 'MagneticField', flow_id: str) -> Dict[str, Any]:
        """Get detailed metrics for a flow"""
        flow_state = field.state.active_flows.get(flow_id)
        if not flow_state:
            return {}
            
        health_monitor = field._health_monitors.get(flow_id)
        if not health_monitor:
            return {}
            
        return {
            "message_rate": flow_state.message_count / max(
                (datetime.now() - flow_state.last_active).total_seconds(), 1
            ) if flow_state.last_active else 0.0,
            "error_rate": health_monitor.error_rate,
            "latency": health_monitor.latency,
            "throughput": health_monitor.throughput,
            "uptime": (datetime.now() - flow_state.last_active).total_seconds() if flow_state.last_active else 0.0
        }
    
    @staticmethod
    def get_protection_status(field: 'MagneticField', flow_id: str) -> Dict[str, Any]:
        """Get detailed status of protection mechanisms for a flow"""
        circuit_breaker = field._circuit_breakers.get(flow_id)
        rate_limiter = field._rate_limiters.get(flow_id)
        retry_strategy = field._retry_strategies.get(flow_id)
        
        return {
            "circuit_breaker": {
                "state": circuit_breaker.state if circuit_breaker else None,
                "error_count": circuit_breaker.error_count if circuit_breaker else 0,
                "last_error": circuit_breaker.last_error if circuit_breaker else None,
                "reset_timeout": circuit_breaker.reset_timeout if circuit_breaker else None
            },
            "rate_limiter": {
                "current_count": rate_limiter.current_count if rate_limiter else 0,
                "max_requests": rate_limiter.max_requests if rate_limiter else None,
                "window_seconds": rate_limiter.window_seconds if rate_limiter else None,
                "window_start": rate_limiter.window_start if rate_limiter else None
            },
            "retry_strategy": {
                "initial_delay": retry_strategy.initial_delay if retry_strategy else None,
                "max_delay": retry_strategy.max_delay if retry_strategy else None,
                "multiplier": retry_strategy.multiplier if retry_strategy else None,
                "jitter": retry_strategy.jitter if retry_strategy else None
            }
        }
