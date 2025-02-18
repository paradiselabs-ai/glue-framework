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
            
        # Update protection status in debug info
        field.debug.update_protection_status(
            flow_id,
            field._circuit_breakers.get(flow_id),
            field._rate_limiters.get(flow_id),
            field._retry_strategies.get(flow_id),
            field._health_monitors.get(flow_id)
        )
        
        # Get protection status from debug info
        protection_status = field.debug.protection_status.get(flow_id, {})
        
        # Create flow debug info
        return FlowDebugInfo(
            flow_id=flow_id,
            source_team=flow_state.config.source,
            target_team=flow_state.config.target,
            flow_type=flow_state.config.flow_type,
            active=field.debug.active_flows.get(flow_id, False),
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
        # Update field's debug info for all active flows
        for flow_id in field.state.active_flows:
            field.debug.update_protection_status(
                flow_id,
                field._circuit_breakers.get(flow_id),
                field._rate_limiters.get(flow_id),
                field._retry_strategies.get(flow_id),
                field._health_monitors.get(flow_id)
            )
            
        # Build active flows info
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
            active_patterns=active_patterns,
            timestamp=datetime.now()
        )
    
    @staticmethod
    def get_flow_metrics(field: 'MagneticField', flow_id: str) -> Dict[str, Any]:
        """Get detailed metrics for a flow"""
        # Update protection status to ensure health metrics are current
        field.debug.update_protection_status(
            flow_id,
            field._circuit_breakers.get(flow_id),
            field._rate_limiters.get(flow_id),
            field._retry_strategies.get(flow_id),
            field._health_monitors.get(flow_id)
        )
        
        # Get flow state
        flow_state = field.state.active_flows.get(flow_id)
        if not flow_state:
            return {}
            
        # Get health metrics from protection status
        protection_status = field.debug.protection_status.get(flow_id, {})
        health_metrics = protection_status.get("health", {})
        
        # Calculate time-based metrics
        now = datetime.now()
        uptime = (now - flow_state.last_active).total_seconds() if flow_state.last_active else 0.0
        message_rate = flow_state.message_count / max(uptime, 1) if uptime > 0 else 0.0
        
        return {
            "message_rate": message_rate,
            "error_rate": health_metrics.get("error_rate", 0.0),
            "latency": health_metrics.get("latency", 0.0),
            "throughput": health_metrics.get("throughput", 0.0),
            "uptime": uptime
        }
    
    @staticmethod
    def get_protection_status(field: 'MagneticField', flow_id: str) -> Dict[str, Any]:
        """Get detailed status of protection mechanisms for a flow"""
        # Update protection status in debug info
        field.debug.update_protection_status(
            flow_id,
            field._circuit_breakers.get(flow_id),
            field._rate_limiters.get(flow_id),
            field._retry_strategies.get(flow_id),
            field._health_monitors.get(flow_id)
        )
        
        # Return protection status from debug info
        return field.debug.protection_status.get(flow_id, {})
