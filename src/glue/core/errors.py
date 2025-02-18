"""Error handling with Pydantic models for GLUE framework"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from .logger import log_error, LogContext

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ErrorCategory(str, Enum):
    """Error categories for better organization"""
    FLOW = "flow"
    TEAM = "team"
    TOOL = "tool"
    MODEL = "model"
    MAGNETIC = "magnetic"
    ADHESIVE = "adhesive"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    RUNTIME = "runtime"
    SYSTEM = "system"

class ErrorContext(BaseModel):
    """Structured error context"""
    timestamp: datetime = Field(default_factory=datetime.now)
    severity: ErrorSeverity
    category: ErrorCategory
    component: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    stack_trace: Optional[str] = None

class GlueError(Exception):
    """Base exception class for GLUE framework"""
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.RUNTIME,
        component: str = "system",
        source: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ):
        self.message = message
        self.context = ErrorContext(
            severity=severity,
            category=category,
            component=component,
            source=source,
            metadata=metadata or {},
            stack_trace=stack_trace
        )
        
        # Log error with context
        log_error(
            error_type=f"{category.value.upper()}_{severity.value.upper()}",
            message=message,
            component=component,
            metadata=self.context.model_dump()
        )
        
        super().__init__(message)

class ValidationError(GlueError):
    """Validation error with Pydantic models"""
    def __init__(
        self,
        message: str,
        component: str,
        invalid_fields: Dict[str, str],
        source: str = "validation",
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata["invalid_fields"] = invalid_fields
        
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.VALIDATION,
            component=component,
            source=source,
            metadata=metadata
        )

class FlowValidationError(GlueError):
    """Flow validation error"""
    def __init__(
        self,
        message: str,
        flow_id: str,
        validation_errors: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "flow_id": flow_id,
            "validation_errors": validation_errors
        })
        
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.VALIDATION,
            component="flow",
            source=f"flow_{flow_id}",
            metadata=metadata
        )

class FlowStateError(GlueError):
    """Flow state error"""
    def __init__(
        self,
        message: str,
        flow_id: str,
        current_state: str,
        expected_state: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "flow_id": flow_id,
            "current_state": current_state,
            "expected_state": expected_state
        })
        
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.FLOW,
            component="flow",
            source=f"flow_{flow_id}",
            metadata=metadata
        )

class FlowError(GlueError):
    """Flow-related errors"""
    def __init__(
        self,
        message: str,
        flow_id: str,
        source_team: str,
        target_team: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "flow_id": flow_id,
            "source_team": source_team,
            "target_team": target_team
        })
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.FLOW,
            component="flow",
            source=f"flow_{flow_id}",
            metadata=metadata
        )

class TeamError(GlueError):
    """Team-related errors"""
    def __init__(
        self,
        message: str,
        team_name: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata["team_name"] = team_name
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.TEAM,
            component="team",
            source=f"team_{team_name}",
            metadata=metadata
        )

class ToolError(GlueError):
    """Tool-related errors"""
    def __init__(
        self,
        message: str,
        tool_name: str,
        adhesive_type: Optional[str] = None,
        team_name: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "tool_name": tool_name,
            "adhesive_type": adhesive_type,
            "team_name": team_name
        })
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.TOOL,
            component="tool",
            source=f"tool_{tool_name}",
            metadata=metadata
        )

class ModelError(GlueError):
    """Model-related errors"""
    def __init__(
        self,
        message: str,
        model_name: str,
        provider: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "model_name": model_name,
            "provider": provider
        })
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.MODEL,
            component="model",
            source=f"model_{model_name}",
            metadata=metadata
        )

class TeamRegistrationError(GlueError):
    """Team registration error"""
    def __init__(
        self,
        message: str,
        team_name: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata["team_name"] = team_name
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.TEAM,
            component="team",
            source=f"team_{team_name}",
            metadata=metadata
        )

class ProtectionMechanismError(GlueError):
    """Protection mechanism error (circuit breaker, rate limiter, etc.)"""
    def __init__(
        self,
        message: str,
        mechanism: str,
        flow_id: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "mechanism": mechanism,
            "flow_id": flow_id
        })
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.FLOW,
            component="protection",
            source=f"protection_{mechanism}",
            metadata=metadata
        )

class PatternValidationError(GlueError):
    """Pattern validation error"""
    def __init__(
        self,
        message: str,
        pattern_name: str,
        validation_errors: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "pattern_name": pattern_name,
            "validation_errors": validation_errors
        })
        
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.VALIDATION,
            component="pattern",
            source=f"pattern_{pattern_name}",
            metadata=metadata
        )

class MagneticError(GlueError):
    """Magnetic field-related errors"""
    def __init__(
        self,
        message: str,
        field_name: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata["field_name"] = field_name
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.MAGNETIC,
            component="magnetic",
            source=f"field_{field_name}",
            metadata=metadata
        )

class ConfigurationError(GlueError):
    """Configuration-related errors"""
    def __init__(
        self,
        message: str,
        config_section: str,
        invalid_values: Dict[str, Any],
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        metadata = metadata or {}
        metadata.update({
            "config_section": config_section,
            "invalid_values": invalid_values
        })
        
        super().__init__(
            message=message,
            severity=severity,
            category=ErrorCategory.CONFIGURATION,
            component="config",
            source=f"config_{config_section}",
            metadata=metadata
        )

def validate_flow_type(flow_type: str, source: str) -> None:
    """Validate flow type"""
    valid_types = ["->", "<-", "><", "<>"]
    if flow_type not in valid_types:
        raise FlowValidationError(
            message=f"Invalid flow type: {flow_type}",
            flow_id=f"validation_{source}",
            validation_errors=[f"Flow type must be one of {valid_types}"]
        )

def validate_team_registered(team_name: str, registered_teams: set, source: str) -> None:
    """Validate team is registered"""
    if team_name not in registered_teams:
        raise TeamRegistrationError(
            message=f"Team {team_name} not registered",
            team_name=team_name
        )

def handle_flow_errors(func):
    """Decorator for handling flow-related errors"""
    from functools import wraps
    import traceback
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except GlueError as e:
            # Already logged in constructor
            raise
        except Exception as e:
            # Get stack trace
            stack_trace = traceback.format_exc()
            
            # Create flow error with stack trace
            raise FlowError(
                message=str(e),
                flow_id=func.__name__,
                source_team="system",
                target_team="system",
                metadata={
                    "args": str(args),
                    "kwargs": str(kwargs),
                    "stack_trace": stack_trace
                }
            ) from e
    
    return wrapper

def error_handler(func):
    """Decorator for handling errors with proper context"""
    from functools import wraps
    import traceback
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except GlueError as e:
            # Already logged in constructor
            raise
        except Exception as e:
            # Get stack trace
            stack_trace = traceback.format_exc()
            
            # Create generic error with stack trace
            raise GlueError(
                message=str(e),
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.RUNTIME,
                component=func.__module__,
                source=func.__name__,
                metadata={
                    "args": str(args),
                    "kwargs": str(kwargs)
                },
                stack_trace=stack_trace
            ) from e
    
    return wrapper
