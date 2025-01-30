"""GLUE Core Types"""

from enum import Enum, auto
from typing import Dict, Set, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

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
    TOOL = auto()        # Tool output/results
    ERROR = auto()       # Error messages

@dataclass
class Message:
    """Message in a conversation"""
    msg_type: MessageType
    sender: str
    receiver: str
    content: Any
    context: Optional['ContextState'] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

class ResourceState(Enum):
    """States for resources"""
    IDLE = auto()     # Resource is available
    ACTIVE = auto()   # Resource is being used

class ToolState(Enum):
    """Tool execution states"""
    IDLE = auto()     # Tool is ready for use
    ACTIVE = auto()   # Tool is currently executing

class AdhesiveType(Enum):
    """Types of adhesive bindings"""
    TAPE = auto()    # One-time use, no persistence
    VELCRO = auto()  # Session-based persistence
    GLUE = auto()    # Team-wide persistence

@dataclass
class ToolResult:
    """Result from a tool execution"""
    tool_name: str
    result: Any
    adhesive: AdhesiveType
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

# Team is defined in team.py to avoid circular imports
