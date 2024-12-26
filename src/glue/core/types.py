"""GLUE Core Types"""

from enum import Enum, auto
from typing import Dict, Set, Optional, Any, List, Protocol, TYPE_CHECKING, Union
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from .context import ContextState

class MessageType(Enum):
    """Types of messages in a conversation"""
    SYSTEM = auto()    # System messages
    USER = auto()      # User messages
    ASSISTANT = auto() # Assistant messages
    TOOL = auto()      # Tool output
    ERROR = auto()     # Error messages
    QUERY = auto()     # Query messages

class WorkflowState(Enum):
    """States of a workflow"""
    IDLE = auto()      # Not running
    RUNNING = auto()   # Currently executing
    PAUSED = auto()    # Temporarily paused
    COMPLETED = auto() # Successfully finished
    FAILED = auto()    # Failed to complete
    CANCELLED = auto() # Manually cancelled

@dataclass
class Message:
    """Message in a conversation"""
    type: MessageType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

class MagneticResource(Protocol):
    """Protocol for resources that can participate in magnetic fields"""
    name: str
    _state: 'ResourceState'
    _context: Optional['ContextState']
    _attracted_to: Set['MagneticResource']
    _repelled_by: Set['MagneticResource']

class ResourceState(Enum):
    """States a resource can be in"""
    IDLE = auto()      # Not currently in use
    ACTIVE = auto()    # Currently in use
    LOCKED = auto()    # Cannot be used by others
    SHARED = auto()    # Being shared between resources
    CHATTING = auto()  # In direct model-to-model communication
    PULLING = auto()   # Receiving data only

@dataclass
class ResourceMetadata:
    """Metadata for a resource"""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    use_count: int = 0
    tags: Set[str] = field(default_factory=set)
    category: str = "default"
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TransitionLog:
    """Log entry for state transition"""
    resource: str
    from_state: ResourceState
    to_state: ResourceState
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None
