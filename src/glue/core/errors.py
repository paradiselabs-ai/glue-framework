"""GLUE Framework Error Handling"""

from typing import Optional, Any, Callable
from datetime import datetime
from pydantic import BaseModel

class ErrorContext(BaseModel):
    """Context information for errors"""
    timestamp: datetime = datetime.now()
    source: str
    details: Optional[dict] = None
    recoverable: bool = True

class GlueError(Exception):
    """Base exception class for GLUE framework"""
    base_message: str = "GLUE Framework Error"
    
    def __init__(
        self,
        message: str,
        source: str,
        details: Optional[dict] = None,
        recoverable: bool = True
    ):
        self.context = ErrorContext(
            source=source,
            details=details,
            recoverable=recoverable
        )
        self.message = f"{self.base_message}: {message}"
        super().__init__(self.message)

class FlowValidationError(GlueError):
    """Error for flow validation failures"""
    base_message = "Flow Validation Error"

class FlowStateError(GlueError):
    """Error for flow state issues"""
    base_message = "Flow State Error"

class TeamRegistrationError(GlueError):
    """Error for team registration issues"""
    base_message = "Team Registration Error"

class ProtectionMechanismError(GlueError):
    """Error for protection mechanism failures"""
    base_message = "Protection Mechanism Error"

class PatternValidationError(GlueError):
    """Error for pattern validation failures"""
    base_message = "Pattern Validation Error"

def handle_flow_errors(func: Callable) -> Callable:
    """Decorator for handling flow-related errors"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, GlueError):
                raise
            raise GlueError(
                message=str(e),
                source=f"{func.__module__}.{func.__name__}",
                details={"args": str(args), "kwargs": str(kwargs)},
                recoverable=True
            ) from e
    return wrapper

def validate_flow_type(flow_type: str) -> None:
    """Validate flow type"""
    if flow_type not in {'><', '->', '<-', '<>'}:
        raise FlowValidationError(
            message=f"Invalid flow type: {flow_type}",
            source="flow_validation",
            details={"flow_type": flow_type},
            recoverable=False
        )

def validate_team_registered(
    team_name: str,
    registered_teams: set,
    source: str
) -> None:
    """Validate team registration"""
    if team_name not in registered_teams:
        raise TeamRegistrationError(
            message=f"Team not registered: {team_name}",
            source=source,
            details={"team_name": team_name},
            recoverable=True
        )
