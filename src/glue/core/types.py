"""GLUE Core Types"""

from enum import Enum, auto
from typing import Dict, Set, Optional, Any, List, Protocol, TYPE_CHECKING, Union, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class IntentAnalysis:
    """Analysis of a prompt's intent and requirements"""
    score: float  # How strongly this team/model should handle the prompt (0-1)
    needed_tools: Set[str] = field(default_factory=set)  # Tools that might be needed
    reasoning: str = ""  # Model's explanation of its analysis
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional context

if TYPE_CHECKING:
    from .context import ContextState

class MessageType(Enum):
    """Types of messages in a conversation"""
    SYSTEM = auto()      # System messages
    USER = auto()        # User messages
    ASSISTANT = auto()   # Assistant messages
    TOOL = auto()        # Tool output
    ERROR = auto()       # Error messages
    QUERY = auto()       # Query messages
    TOOL_REQUEST = auto()  # Tool request messages
    TOOL_RESULT = auto()  # Tool result messages
    RESPONSE = auto()     # Response messages
    WORKFLOW = auto()     # Workflow messages
    SYNC = auto()        # Synchronization messages

@dataclass
class Message:
    """Message in a conversation"""
    msg_type: MessageType
    sender: str
    receiver: str
    content: Any
    context: Optional['ContextState'] = None
    workflow_id: Optional[str] = None
    requires_response: bool = False
    response_timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

class MagneticResource(Protocol):
    """Protocol for resources that can participate in magnetic fields"""
    name: str
    team: str
    _attracted_to: Set['MagneticResource']
    _repelled_by: Set['MagneticResource']

class InteractionPattern(Enum):
    """Patterns for resource interaction"""
    ATTRACT = "><"  # Bidirectional attraction (full coupling)
    PUSH = "->"    # One-way push (directed flux)
    PULL = "<-"    # Fallback pull (only if push fails or more data needed)
    REPEL = "<>"   # Repulsion (enforced boundary)

    @property
    def is_pull_allowed(self) -> bool:
        """Check if pull is allowed based on pattern"""
        return self in {self.ATTRACT, self.PULL}  # Pull allowed for ATTRACT and PULL patterns

    @property
    def is_push_allowed(self) -> bool:
        """Check if push is allowed based on pattern"""
        return self in {self.ATTRACT, self.PUSH}  # Push allowed for ATTRACT and PUSH patterns

class ResourceState(Enum):
    """States for resources"""
    IDLE = auto()     # Resource is available
    ACTIVE = auto()   # Resource is being used

class BindingState(Enum):
    """States for bindings"""
    ACTIVE = auto()    # Binding is active and usable
    DEGRADED = auto()  # Binding is weakened but still usable
    FAILED = auto()    # Binding has failed and needs to be recreated

class AdhesiveState(Enum):
    """States for adhesive bindings"""
    INACTIVE = auto()  # Not yet activated
    ACTIVE = auto()    # Ready for use
    DEGRADED = auto()  # Weakened but still usable
    EXPIRED = auto()   # No longer usable

class AdhesiveType(Enum):
    """Types of adhesive bindings"""
    TAPE = auto()    # One-time use, no persistence
    VELCRO = auto()  # Session-based persistence
    GLUE = auto()    # Team-wide persistence

@dataclass
class AdhesiveProperties:
    """Properties for adhesive bindings"""
    strength: float = 1.0
    durability: float = 1.0
    flexibility: float = 1.0
    duration: Optional[timedelta] = None
    is_reusable: bool = True
    max_uses: Optional[int] = None
    allowed_patterns: Set[InteractionPattern] = field(default_factory=set)
    resource_pool: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolResult:
    """Result from a tool execution"""
    tool_name: str
    result: Any
    adhesive: AdhesiveType
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TransitionLog:
    """Log entry for a state transition"""
    resource: str
    from_state: ResourceState
    to_state: ResourceState
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None

@dataclass
class WorkflowState:
    """State of a multi-model workflow"""
    workflow_id: str
    initiator: str
    participants: Set[str]
    current_stage: str
    context: Optional['ContextState']
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class ResourceMetadata:
    """Resource metadata"""
    category: str
    tags: Set[str] = field(default_factory=set)

# Team is defined in team.py to avoid circular imports
